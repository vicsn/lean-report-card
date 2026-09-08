# Security model and limitations

Analyzing a repository means executing attacker-controlled build configuration, compiler plugins, macros, elaborators, native code and shell commands. Treat every analyzed repository as hostile.

Analyses now run **as a local subprocess with no sandbox**. `runner/analyze.py` clones a repository and runs `lake build` with the full privileges of the invoking user, on the invoking user's filesystem and network. The only enforced limits are a resident-memory ceiling and a wall-clock timeout, applied by polling the process tree and killing the process group.

This is acceptable for a maintainer scoring repositories they have chosen to trust. It is **not safe for unattended or public use**:

- there is no filesystem, network or privilege boundary between an analyzed project and the host;
- Elan and Lake require outbound network access, so build steps fetch and execute remote code;
- shared Elan and Lake caches persist between jobs and can become a cross-job channel;
- memory and time ceilings do not prevent data exfiltration, credential theft or persistence;
- the website's form endpoints are unauthenticated Cloudflare Worker routes that email submissions to the maintainers. They validate field shape and length only; they have no captcha, quota or per-IP rate limit, so a bot can flood the notification mailbox.

Run analyses inside a disposable VM if you intend to score repositories you have not reviewed. Before accepting public submissions, move untrusted analyses to ephemeral VMs or a hardened sandbox such as gVisor/Kata, with minimal identity, controlled egress, disposable caches, dependency provenance checks, strict quotas and automatic teardown.
