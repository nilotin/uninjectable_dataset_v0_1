# Provenance Rules v0.1

For every externally derived example, record:
- source dataset name;
- original record ID when available;
- how the source was used (e.g. attack-language seed, benign-user-message seed, tool-structure seed);
- transformation performed;
- upstream license in a separate source manifest.

Never assume the repository license automatically applies to every embedded dataset artifact.
Keep a local copy of the relevant dataset card/license notice when importing a source.

Recommended raw-source manifest fields:
- source_name
- source_url
- retrieved_at
- artifact_path
- license_identifier
- license_file_path
- allowed_use_notes
- attribution_text
