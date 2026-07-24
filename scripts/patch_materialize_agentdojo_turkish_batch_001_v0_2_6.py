from pathlib import Path


SOURCE_PATH = Path(
    "scripts/"
    "materialize_agentdojo_turkish_batch_001_v0_2_5.py"
)

OUTPUT_PATH = Path(
    "scripts/"
    "materialize_agentdojo_turkish_batch_001_v0_2_6.py"
)


def replace_exactly_once(
    text: str,
    old: str,
    new: str,
    description: str,
) -> str:

    count = text.count(old)

    if count != 1:
        raise ValueError(
            f"{description}: expected exactly one "
            f"match, found {count}."
        )

    return text.replace(
        old,
        new,
        1,
    )


def main() -> None:

    if not SOURCE_PATH.exists():
        raise FileNotFoundError(
            f"Missing source script: {SOURCE_PATH}"
        )

    text = SOURCE_PATH.read_text(
        encoding="utf-8"
    )

    # Yeni artifact sürümü.
    text = text.replace(
        "v0.2.5",
        "v0.2.6",
    )

    old_sections = '''    sections = {
        "USER_GOAL": (
            translation["user_goal_tr"]
        ),
        "USER_AUTHORIZATION": (
            translation[
                "user_authorization_tr"
            ]
        ),
        "ATTEMPTED_ACTION": (
            attempted_action_tr
        ),
        "RETRIEVED_CONTENT": (
            translation[
                "retrieved_content_tr"
            ]
        ),
        "SOURCE": "\\n".join(
            source_lines
        ),
        "AGENT_FACTS": agent_facts,
    }

    order = (
        "USER_GOAL",
        "USER_AUTHORIZATION",
        "ATTEMPTED_ACTION",
        "RETRIEVED_CONTENT",
        "SOURCE",
        "AGENT_FACTS",
    )
'''

    new_sections = '''    # USER_GOAL full structured artifact içinde korunur.
    # Compact BERT view'da ise daha kesin olan
    # USER_AUTHORIZATION alanıyla tekrar ettiği için çıkarılır.
    sections = {
        "USER_AUTHORIZATION": (
            translation[
                "user_authorization_tr"
            ]
        ),
        "ATTEMPTED_ACTION": (
            attempted_action_tr
        ),
        "RETRIEVED_CONTENT": (
            translation[
                "retrieved_content_tr"
            ]
        ),
        "SOURCE": "\\n".join(
            source_lines
        ),
        "AGENT_FACTS": agent_facts,
    }

    order = (
        "USER_AUTHORIZATION",
        "ATTEMPTED_ACTION",
        "RETRIEVED_CONTENT",
        "SOURCE",
        "AGENT_FACTS",
    )
'''

    text = replace_exactly_once(
        text,
        old_sections,
        new_sections,
        "compact section patch",
    )

    old_removed_sections = '''                    "removed_sections": [
                        "CONTEXT_BINDINGS",
                        "POLICY_CONTEXT",
                        "full_allowed_tools",
                    ],
'''

    new_removed_sections = '''                    "removed_sections": [
                        "USER_GOAL",
                        "CONTEXT_BINDINGS",
                        "POLICY_CONTEXT",
                        "full_allowed_tools",
                    ],
'''

    text = replace_exactly_once(
        text,
        old_removed_sections,
        new_removed_sections,
        "removed-sections metadata patch",
    )

    OUTPUT_PATH.write_text(
        text,
        encoding="utf-8",
    )

    print(
        "Created:",
        OUTPUT_PATH,
    )

    print(
        "Compact USER_GOAL removed: yes"
    )

    print(
        "Full structured USER_GOAL preserved: yes"
    )

    print(
        "Source v0.2.5 script modified: no"
    )


if __name__ == "__main__":
    main()
