# Amplifier TUI

Use Amplifier Unified from your terminal. Keep a terminal and web tabs open on
the same conversation, follow the same work, and keep a separate draft in each
view. Closing the terminal leaves work running on the host.

## Get started

You need a running [Amplifier Unified](https://github.com/microsoft/amplifier-unified)
host with the connected-client interface (Unified 0.19.5 or later).

From source, install with Python 3.11+, uv, Git, Rust/Cargo and a C linker:

```sh
uv tool install --no-sources git+https://github.com/microsoft/amplifier-app-tui
amplifier-tui --server http://127.0.0.1:8941
```

Native builds support macOS and Linux; Windows uses WSL2. A compatible prebuilt
wheel from [Releases](https://github.com/microsoft/amplifier-app-tui/releases)
does not need a compiler. Choose a connected-client release; older 0.3 wheels
are the standalone application.

For a local host, the client finds its control token in the normal Unified home.
For a remote host, use verified HTTPS and private token/certificate files:

```sh
amplifier-tui --server https://host.example:8443 \
  --token-file /private/host-token --ca-file /private/host-ca.crt
```

## Use the terminal

- **Enter** sends; **Alt+Enter** adds a newline. Pasting does not send.
- Run `amplifier-tui --resume` to choose a saved conversation, or use
  `--session HOST_CONVERSATION_ID` to open one directly.
- Run `amplifier-tui --new` for a new conversation. For a remote host, use
  `--workspace /path/on/the/host` when its project path differs from your local path.
- **Stop** requests cancellation; it does not undo work already performed.
- **Ctrl-Q** detaches. Reconnecting does not resend an uncertain request;
  `/deliveries` lets you inspect it.

This client focuses on conversation and work status. Attachments, rich artifacts,
voice, configuration editing and full Canvas interaction use the web client.

## Learn more

- [Connection, recovery and client behavior](notes/CONNECTED-CLIENT.md)
- [Standalone use](docs/STANDALONE.md), without a Unified host
- [Contributor checks](SMOKE_TESTS.md) and [working instructions](AGENTS.md)

## Contributing

Most contributions require you to agree to a
Contributor License Agreement (CLA) declaring that you have the right to, and actually do, grant us
the rights to use your contribution. For details, visit [Contributor License Agreements](https://cla.opensource.microsoft.com).

When you submit a pull request, a CLA bot will automatically determine whether you need to provide
a CLA and decorate the PR appropriately (e.g., status check, comment). Simply follow the instructions
provided by the bot. You will only need to do this once across all repos using our CLA.

This project has adopted the [Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/).
For more information see the [Code of Conduct FAQ](https://opensource.microsoft.com/codeofconduct/faq/) or
contact [opencode@microsoft.com](mailto:opencode@microsoft.com) with any additional questions or comments.

## Trademarks

This project may contain trademarks or logos for projects, products, or services. Authorized use of Microsoft
trademarks or logos is subject to and must follow
[Microsoft's Trademark & Brand Guidelines](https://www.microsoft.com/legal/intellectualproperty/trademarks/usage/general).
Use of Microsoft trademarks or logos in modified versions of this project must not cause confusion or imply Microsoft sponsorship.
Any use of third-party trademarks or logos are subject to those third-party's policies.
