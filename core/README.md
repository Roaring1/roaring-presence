# Core publisher

The core is the optional Discord-facing part of roaring-presence. It owns one
local Discord IPC connection and arbitrates independent providers; it does not
read CD drives, inspect game instances, download metadata, or render artwork.
The standalone CD player has no dependency on this component.

## Lifecycle

- `roaring-presenced.socket` is a passive user-level Unix socket.
- systemd starts `roaring-presenced` when a provider connects.
- providers identify themselves and send an activity payload.
- the highest-priority provider with a non-null activity is published.
- when the last provider disconnects, the manager clears Discord activity,
  closes the connection, and exits after `idle_exit_seconds` (one second in
  the sample config).

The service itself is not enabled as a permanent daemon. Enabling the socket
is expected and inexpensive; it is the activation endpoint.

## Provider wire protocol

Connect to `$XDG_RUNTIME_DIR/roaring-presence.sock` and send one JSON object
per line:

```json
{"provider":"cd","priority":50,"activity":{"details":"Listening to ..."}}
{"provider":"cd","activity":null}
{"cmd":"ping"}
{"cmd":"status"}
```

A provider connection has an identity for its lifetime. It can update its
name/priority and activity. Closing the connection removes that provider.
Only the manager speaks Discord IPC.

`status` returns whether Discord is connected, provider identities and
priorities, and the current winner. The socket is mode `0600`; it is intended
for providers running as the same Unix user, not as a network service.

## Commands

`roaring-presence-doctor` is a read-only diagnostic. By default it checks the
socket path without connecting, so it does not trigger systemd activation.
`roaring-presence-doctor --query-manager` explicitly connects and can activate
the manager socket if systemd is listening.
`roaring-presenced --debug` increases manager logging.

## Configuration

The shared config contains:

- `client_id`: public Discord Application ID;
- `ipc_socket_candidates`: ordered local Discord/Vesktop socket paths;
- `priorities`: provider arbitration priorities;
- `idle_exit_seconds`: idle cleanup grace;
- `log_level`.

Providers share this file but own their own feature-specific settings.

## Extension contract

A new provider should:
1. do its source-specific detection independently;
2. connect only for the useful lifetime of its source session;
3. send an initial activity and only meaningful changes;
4. send `activity: null` before an orderly disconnect when possible;
5. close its socket on exit, allowing the manager to exit when unused.

Do not put provider-specific polling, network lookup, or device code in the
core. See [the architecture note](../docs/architecture.md).
