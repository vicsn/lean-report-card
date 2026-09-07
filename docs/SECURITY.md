# Security model and limitations

Analyzing a repository means executing attacker-controlled build configuration, compiler plugins, macros, elaborators, native code and shell commands. Treat every submitted repository as hostile.

The scaffold reduces obvious risk by accepting only public GitHub HTTPS URLs, resolving exact commits before execution, using disposable runner containers, dropping Linux capabilities, enabling `no-new-privileges`, bounding CPU/RAM (no extra swap)/PIDs/time, limiting captured logs and separating small/big worker concurrency.

It is **not safe for an unrestricted public production service yet**:

- workers mount the Docker socket, which is effectively host-root authority;
- analyzer containers have outbound network access for Elan and Lake downloads;
- the default Docker runtime is not a hardened VM or sandbox boundary;
- shared Elan and dependency caches can become a cross-job channel;
- no submission authentication, quotas, rate limiting, malware scanning or abuse workflow exists;
- no egress allowlist, per-job service account, provenance verification or secretless build proof exists;
- resource limits do not prevent all kernel, Docker daemon or dependency-supply-chain attacks;
- the website's form endpoints are unauthenticated Cloudflare Pages Functions that email submissions to the maintainers. They validate field shape and length only; they have no captcha, quota or per-IP rate limit, so a bot can flood the notification mailbox.

Before public launch, move untrusted analyses to ephemeral VMs or a hardened sandbox such as gVisor/Kata with no Docker socket, minimal identity, controlled egress, disposable caches, image and dependency provenance checks, strict quotas and automatic teardown. Keep the web/database control plane separate from executors.
