import os
import json
import openai
from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client
from typing import List
import asyncio
import nest_asyncio

# Intentar cargar variables de entorno desde .env si existe
try:
    from load_env import load_env_file

    load_env_file()
except ImportError:
    # load_env.py no existe, usar variables del sistema
    pass

nest_asyncio.apply()


class MCP_ChatBot:

    def __init__(self):
        # Initialize session and client objects
        self.session: ClientSession = None

        # OpenAI client initialization
        # IMPORTANTE: Debes configurar tu API key aquí

        try:
            # Opción recomendada: usar variable de entorno
            api_key = os.getenv('OPENAI_API_KEY')

            if not api_key:
                # Si no hay variable de entorno, mostrar error claro
                raise ValueError("OPENAI_API_KEY no encontrada en variables de entorno")

            # Inicializar cliente OpenAI
            self.client = openai.OpenAI(api_key=api_key)
            print(" Cliente OpenAI inicializado correctamente")

        except Exception as e:
            print(f"  Error inicializando OpenAI: {e}")
            print("   Para configurar tu API key:")
            print("   Windows: set OPENAI_API_KEY=tu-api-key")
            print("   Linux/Mac: export OPENAI_API_KEY=tu-api-key")
            print("   O crea un archivo .env con: OPENAI_API_KEY=tu-api-key")
            raise

        self.available_tools: List[dict] = []

    def convert_tools_to_openai_format(self, mcp_tools):
        """Convierte herramientas de MCP al formato de OpenAI"""
        openai_tools = []

        for tool in mcp_tools:
            openai_tool = {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["input_schema"]  # MCP usa input_schema, OpenAI usa parameters
                }
            }
            openai_tools.append(openai_tool)

        return openai_tools

    async def process_query(self, query):
        messages = [{'role': 'user', 'content': query}]

        # Convertir herramientas al formato de OpenAI
        openai_tools = self.convert_tools_to_openai_format(self.available_tools)

        response = self.client.chat.completions.create(
            model='gpt-4o',  # o 'gpt-4-turbo', 'gpt-3.5-turbo'
            messages=messages,
            tools=openai_tools,  # herramientas en formato OpenAI
            tool_choice='auto',
            max_tokens=2024,
            temperature=0.1
        )

        process_query = True
        iteration = 0
        max_iterations = 10  # Prevenir loops infinitos

        while process_query and iteration < max_iterations:
            iteration += 1
            message = response.choices[0].message

            # Si hay contenido de texto
            if message.content:
                print(f"\n Asistente: {message.content}")

            # Si hay llamadas a herramientas
            if message.tool_calls:
                print(f"\n Detectadas {len(message.tool_calls)} llamadas a herramientas:")

                # Agregar el mensaje del asistente
                messages.append({
                    "role": "assistant",
                    "content": message.content,
                    "tool_calls": message.tool_calls
                })

                # Procesar cada herramienta
                for tool_call in message.tool_calls:
                    tool_name = tool_call.function.name
                    try:
                        tool_args = json.loads(tool_call.function.arguments)
                    except json.JSONDecodeError as e:
                        print(f" Error parsing tool arguments: {e}")
                        continue

                    tool_id = tool_call.id

                    print(f"⚡ Llamando {tool_name} con argumentos: {tool_args}")

                    try:
                        # Llamada a herramienta a través de MCP session
                        result = await self.session.call_tool(tool_name, arguments=tool_args)

                        # Manejar diferentes tipos de contenido de resultado
                        if hasattr(result, 'content'):
                            if isinstance(result.content, list):
                                # Si es una lista, unir los contenidos
                                tool_result = "\n".join([
                                    item.text if hasattr(item, 'text') else str(item)
                                    for item in result.content
                                ])
                            else:
                                tool_result = str(result.content)
                        else:
                            tool_result = str(result)

                        print(f" Resultado: {tool_result[:200]}..." if len(
                            tool_result) > 200 else f" Resultado: {tool_result}")

                    except Exception as e:
                        tool_result = f"Error calling tool: {str(e)}"
                        print(f" Error: {tool_result}")

                    # Agregar resultado al historial de mensajes
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_id,
                        "content": tool_result
                    })

                # Nueva llamada con los resultados de las herramientas
                response = self.client.chat.completions.create(
                    model='gpt-4o',
                    messages=messages,
                    tools=openai_tools,
                    tool_choice='auto',
                    max_tokens=2024,
                    temperature=0.1
                )

                # Verificar si la nueva respuesta es solo texto (sin más tool calls)
                new_message = response.choices[0].message
                if new_message.content and not new_message.tool_calls:
                    print(f"\n Asistente: {new_message.content}")
                    process_query = False
            else:
                # No hay más llamadas a herramientas
                process_query = False
                if not message.content:
                    print(" No se recibió contenido del asistente")

    async def chat_loop(self):
        """Run an interactive chat loop"""
        print("\n MCP Chatbot Iniciado! (Versión OpenAI)")
        print("=" * 60)
        print(" Herramientas disponibles:", [tool["name"] for tool in self.available_tools])
        print(" Escribe tus consultas o 'quit' para salir.")
        print("=" * 60)

        while True:
            try:
                query = input("\n Tu consulta: ").strip()

                if query.lower() in ['quit', 'exit', 'q', 'salir']:
                    print(" ¡Adiós!")
                    break

                if not query:
                    print(" Por favor ingresa una consulta.")
                    continue

                print(f"\n Procesando: '{query}'")
                await self.process_query(query)
                print("\n" + "─" * 60)

            except KeyboardInterrupt:
                print("\n ¡Adiós!")
                break
            except Exception as e:
                print(f"\n Error: {str(e)}")

    async def connect_to_server_and_run(self):
        """Conectar al servidor MCP y ejecutar el chatbot"""
        # Create server parameters for stdio connection
        server_params = StdioServerParameters(
            command="python",  # CAMBIADO: de "uv" a "python"
            args=["research_server.py"],  # CAMBIADO: de ["run", "research_server.py"] a ["research_server.py"]
            env=None,  # Optional environment variables
        )

        print("🔌 Conectando al servidor MCP...")

        try:
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    self.session = session

                    # Initialize the connection
                    print("⚡ Inicializando conexión...")
                    await session.initialize()

                    # List available tools
                    print(" Descubriendo herramientas disponibles...")
                    response = await session.list_tools()

                    tools = response.tools
                    print(f"\n Conectado al servidor con {len(tools)} herramientas:")
                    for tool in tools:
                        print(f"  - {tool.name}: {tool.description}")

                    # Convertir herramientas al formato interno
                    self.available_tools = [{
                        "name": tool.name,
                        "description": tool.description,
                        "input_schema": tool.inputSchema
                    } for tool in response.tools]

                    # Verificar formato de herramientas
                    print(f"\n Herramientas convertidas al formato OpenAI: {len(self.available_tools)}")
                    openai_tools = self.convert_tools_to_openai_format(self.available_tools)
                    print(" Vista previa de herramientas OpenAI:")
                    for tool in openai_tools:
                        print(f"  - {tool['function']['name']}")

                    await self.chat_loop()

        except Exception as e:
            print(f" Error conectando al servidor MCP: {e}")
            print("\n Posibles soluciones:")
            print("1. Asegúrate de que research_server.py existe en la misma carpeta")
            print("2. Verifica que el entorno virtual esté activado")
            print("3. Confirma que las dependencias están instaladas")

    async def test_openai_connection(self):
        """Test OpenAI API connection"""
        try:
            test_response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": "Hello, test connection"}],
                max_tokens=10
            )
            print(" Conexión a OpenAI API exitosa")
            return True
        except Exception as e:
            print(f" Error en conexión a OpenAI API: {e}")
            print("\n Posibles soluciones:")
            print("1. Verifica tu API key: set OPENAI_API_KEY=tu-api-key")
            print("2. Confirma que tienes créditos suficientes")
            print("3. Verifica conexión a internet")
            return False


async def main():
    print(" Iniciando MCP ChatBot...")

    try:
        chatbot = MCP_ChatBot()

        # Test OpenAI connection first
        print(" Probando conexión a OpenAI...")
        if not await chatbot.test_openai_connection():
            print("\n No se puede continuar sin conexión a OpenAI")
            return

        # Connect to MCP server and run
        await chatbot.connect_to_server_and_run()

    except Exception as e:
        print(f" Error en inicialización: {e}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n Chatbot terminado por usuario")
    except Exception as e:
        print(f" Error fatal: {e}")