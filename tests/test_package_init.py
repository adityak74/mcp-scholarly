from unittest.mock import MagicMock, patch

import mcp_scholarly


def test_main_runs_server_main_via_asyncio():
    # server.main() must NOT be awaited here -- __init__.main() passes the
    # coroutine object straight to asyncio.run, which awaits it itself.
    server_main_mock = MagicMock(return_value="server-main-coroutine")

    with patch.object(mcp_scholarly.asyncio, "run") as run_mock, \
         patch.object(mcp_scholarly.server, "main", server_main_mock):
        mcp_scholarly.main()

    server_main_mock.assert_called_once_with()
    run_mock.assert_called_once_with("server-main-coroutine")
