# vis-network (vendored)

Graph drawing for the Netzwerk page (`network/templates/network/graph.html`).
Served from `/static/` because the portal's CSP allows `script-src 'self'` only.

| File | Package | Version | Source in the npm tarball |
|---|---|---|---|
| `vis-network.min.js` | vis-network | 9.1.9 | `peer/umd/vis-network.min.js` |
| `vis-network.min.css` | vis-network | 9.1.9 | `styles/vis-network.min.css` |
| `vis-data.min.js` | vis-data | 7.1.9 | `peer/umd/vis-data.min.js` |

The *peer* build is used on purpose: the *standalone* build injects its CSS
through a `<style>` element, which `style-src 'self'` refuses. The trailing
`sourceMappingURL` comments were removed (the `.map` files are not shipped and
`collectstatic` would fail on the dangling references).

License: dual Apache-2.0 / MIT (`LICENSE-APACHE-2.0`, `LICENSE-MIT`).
To update, replace the three files from the same paths of the new tarballs and
strip the `sourceMappingURL` lines again.
