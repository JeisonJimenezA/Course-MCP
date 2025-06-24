import asyncio
from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client

# Create server parameters for stdio connection
server_params = StdioServerParameters(
    command="python",  # Cambiado de "uv" a "python"
    args=["research_server.py"],  # Cambiado de ["run example_server.py"] a ["research_server.py"]
    env=None,  # Optional environment variables
)


async def run():
    print("🔌 Conectando al servidor MCP...")

    # Launch the server as a subprocess & returns the read and write streams
    async with stdio_client(server_params) as (read, write):
        print("✅ Servidor iniciado")

        # the client session is used to initiate the connection
        async with ClientSession(read, write) as session:
            print("🤝 Inicializando sesión...")

            # Initialize the connection (1:1 connection with the server)
            await session.initialize()
            print("✅ Conexión inicializada")

            # List available tools
            print("🛠️ Listando herramientas disponibles...")
            tools_response = await session.list_tools()
            tools = tools_response.tools

            print(f"📋 Herramientas encontradas: {len(tools)}")
            for tool in tools:
                print(f"  - {tool.name}: {tool.description}")

            # Test: Call search_papers tool
            print("\n🔍 Probando herramienta search_papers...")
            result = await session.call_tool(
                "search_papers",
                arguments={"topic": "machine learning", "max_results": 2}
            )
            print(f"✅ Resultado: {result.content}")

            # Test: Call extract_info tool
            print("\n📄 Probando herramienta extract_info...")
            result2 = await session.call_tool(
                "extract_info",
                arguments={"paper_id": "test-id"}
            )
            print(f"✅ Resultado: {result2.content}")


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        print("\n👋 Cliente terminado por usuario")
    except Exception as e:
        print(f"❌ Error: {e}")