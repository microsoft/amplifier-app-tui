# Unified client adoption and boundary proposal

Authority: the user requested that amplifier-app-tui become a Unified client and
an optional installation. The existing contracts remain DRAFT. Shared direction
is referenced at Unified PR 153 / 31a74c7c, not copied or claimed ratified here.

The connected path owns five small modules: launch, private client intent,
HTTP/SSE transport, projection and the terminal protocol adapter. It does not
import the standalone execution host. Ordinary package dependencies contain only
the transport; the existing host and historical Textual harness dependencies move
to the explicit `standalone` extra. Ratatui is unchanged as the chosen frontend.

This creates two explicit responsibilities inside one repository: connected
presentation and optional standalone execution. A physical package/repository
split is proposed when the standalone host next needs independent release work;
that extraction would preserve its existing tests and entrypoint rather than
copy host policy into the client. This change does not silently delete that mode.
The DRAFT source ceiling changes from 50 to 55 for these five boundary modules;
this is recorded explicitly rather than hiding files from the structure check.
No further growth is authorized by this proposal, and exceeding that boundary
still requires a new split proposal under composition.v1:5.

First supported connected operations: host conversation listing, creation,
selection, rename, bounded history, text send, streamed/final responses, approval
answers, host Stop, takeover, deliberate exact retry and detach. Remote workspace
paths stay on the host. Each terminal has a unique presentation identity; an
explicit recovery ID is locally locked against concurrent use. Credentials remain
outside client state and command arguments. Remote HTTPS validates the server,
including an explicitly supplied CA.

Queue/steer, standalone graceful/force semantics, provider/module catalogs,
local file attachments and full rich-canvas rendering are not silently emulated.
Unavailable controls explain the boundary. Unknown delivery retains the exact
request; reconnect only reads. Client-state files contain intent and drafts, not
canonical history or provider credentials. The server remains responsible for
native session storage and the Foundation execution lock.

Acceptance must use the actual terminal entrypoint and a real Unified HTTP/SSE
service, separately from protocol fixtures. Record exact builds and remaining
limits in ACCEPTANCE.md. No production deployment is part of source qualification.
