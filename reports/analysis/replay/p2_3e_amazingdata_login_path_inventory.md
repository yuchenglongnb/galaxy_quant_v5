# P2.3E AmazingData Login Path Inventory

## Scope

This inventory reviews existing AmazingData login call shapes in the repository. It records call style only and does not include credential values, host values, port values, supplier logs, or market data.

## Inventory

| path | login_call_style | uses_build_login_invocation | uses_keyword_int_port | uses_direct_args | uses_context_process | known_working | notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `core/amazing_login_client.py` | shared helper styles | yes | yes | no | no | no | Provides `keyword-int-port`, `keyword-str-port`, `positional-int-port`, and `positional-str-port`; current worker path hits `SystemExit(0)`. |
| `scripts/check_amazingdata_login.py` | isolated login check / differential trace | yes | yes | no | yes | no | Existing differential report also recorded `SystemExit(0)` for int-port styles. |
| `scripts/probe_amazingdata_query_modes.py` | explicit login continue/strict plus implicit query comparison | yes | yes | no | yes | partial query probe path | Useful later if login semantics remain odd, but P2.3E stays login-only. |
| `scripts/collect_0935_feedback.py` | historical 09:35 collection login | yes | yes by default | no | optional subprocess | no | P2.3E adds configurable `--login-style`; no query attempted without successful login-only probe. |
| `scripts/amazing_0935_preflight_probe.py` | staged preflight login | yes | yes by default | no | subprocess worker | no | P2.3D located first failing stage as `login`. |
| `scripts/amazing_0935_query_worker.py` | historical query worker login | yes | yes by default | no | subprocess worker | no | P2.3E adds configurable login style support. |
| `runners/base.py` | direct settings-based login | no | unknown | yes | runtime runner | not tested in P2.3E | Uses project `DBConfig`; not used for 09:35 backfill in this PR. |
| `scripts/inspect_kline_debug.py` | direct settings-based login | no | unknown | yes | debug script | not tested in P2.3E | Debug path only; not used for temporal feedback backfill. |
| `scripts/verify_snapshot_history.py` | direct settings-based login | no | unknown | yes | debug script | not tested in P2.3E | Snapshot diagnostic path; not used in P2.3E. |
| `test_api.py` | bootstrap helper via `do_login` / trace mode | yes | yes | no | CLI diagnostic | no | Historical trace showed `SystemExit(0)` as well. |

## Current Conclusion

P2.3E tests five isolated styles:

```text
style_a_build_login_invocation_keyword_int_port
style_b_build_login_invocation_positional_int_port
style_c_direct_keyword_args
style_d_positional_args
style_e_existing_project_helper_exact
```

All five styles return `SystemExit(0)` in the current environment. This is classified as ambiguous SDK login control flow, not as a successful login.
