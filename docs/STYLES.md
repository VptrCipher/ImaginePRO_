# ImaginePro style library

ImaginePro includes four user-requested project skills in the Styles menu and AI
style selector. Each View button opens its original Markdown read-only.
Selecting a guide sends its full instructions as creative
context to the restricted edit planner and original-scene composer. No skill code is executed and no
external animation tools are installed by selecting a style.

- [Hand-drawn Cartoon](https://github.com/PHANTOMTONYT/motion-design-skills/blob/main/hand-drawn-cartoon/SKILL.md): warm paper, ink and storybook pacing.
- [Apple Launch Film](https://github.com/charlie947/motion-graphics-skills/blob/main/skills/apple-launch-film/SKILL.md): restrained product storytelling and deliberate reveals.
- [Vox Explainer](https://github.com/charlie947/motion-graphics-skills/blob/main/skills/vox-explainer/SKILL.md): editorial hierarchy and documentary rhythm.
- [Kinetic Typography](https://github.com/PHANTOMTONYT/motion-design-skills/blob/main/kinetic-typography/SKILL.md): type-led storytelling and short emphatic phrases.

The unchanged upstream SKILL.md files and each repository's MIT LICENSE are kept
in `skills/<slug>/`. `skills/catalog.json` adds display names, concise descriptions,
source links and the checked upstream commit. Registry identifiers still derive
from paths, preserving existing selections. This is a project library; the user's
global Codex skill configuration is unchanged. Styles are immediately discoverable
by the running app after refresh.

These guides influence cuts, captions, typography, illustration, character poses
and scene timing. Their full examples use engines such as HyperFrames/GSAP that
ImaginePro does not run. Codex adapts the visual language into the app's validated
scene graph: original curved paths/shapes, parented character parts, interface-like
widgets, text and animated transforms. Style fidelity depends on the prompt and
the supported drawing primitives; importing Markdown does not install its engines.
Framecraft remains the default guide. Its older curated bloom preset is also
available to existing timelines, independently of new scene generation.

The ImaginePro rebrand changes the wordmark, favicon, document title, launch label,
style presentation and CSS theme. `editor-base.css` retains the existing control
layout; `imaginepro.css` supplies the new glass surfaces, midnight palette and mint
accent. Both desktop and narrow layouts preserve video/audio timeline controls.
The existing API paths, local-storage project key, client header, SQLite data and
media locations remain compatible, and Start Studio.cmd remains a launch alias.
