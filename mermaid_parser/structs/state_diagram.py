from typing import Optional, Union
from mermaid.statediagram import StateDiagram
from mermaid.statediagram.state import State, Start, End
from mermaid.statediagram.base import BaseTransition
from mermaid import Direction
from mermaid.configuration import Config


class Note:
    def __init__(self, content: str, target_state: State, position: str) -> None:
        self.content: str = content
        self.target_state: State = target_state
        self.position: str = position

    def __str__(self):
        return (
            f"note {self.position} {self.target_state.id_}\n\t{self.content}\nend note"
        )


class StateDiagramWithNote(StateDiagram):
    """
    Extending the StateDiagram class from mermaid with note support.
    """

    def __init__(
        self,
        title: str,
        states: Optional[list[State]] = [],
        notes: Optional[list[Note]] = [],
        transitions: Optional[list[BaseTransition]] = [],
        version: str = "v2",
        direction: Optional[Union[str, Direction]] = None,
        config: Optional[Config] = None,
    ) -> None:
        """StateDiagramWithNote

        Args:
            title (str): Title of the stateDiagram.
            states (list[State]): List of states.
            notes (list[Note]): List of notes.
            transitions (list[BaseTransition]): List of transitions.
            version (str, optional): Version of the stateDiagram. Defaults to 'v2'.
            direction (Optional[Union[str,Direction]], optional): Direction of the stateDiagram. Defaults to None.
            config (Optional[Config], optional): Configuration for the stateDiagram. Defaults to None.
        """  # noqa E501
        self.notes = notes
        super().__init__(title, states, transitions, version, direction, config)

    def _build_script(self) -> None:
        script: str = f"---\ntitle: {self.title}\n---"
        if self.config:
            script += "\n" + str(self.config)
        str_version: str = f"-{self.version}" if self.version != "v1" else ""
        script += f"\nstateDiagram{str_version}"
        if self.direction:
            script += f"\n\tdirection {self.direction}"
        for style in self.styles:
            script += f"\n\t{style}"
        for state in self.states:
            if isinstance(state, Start) or isinstance(state, End):
                continue
            script += f"\n\t{state}"
        for transition in self.transitions:
            script += f"\n\t{transition}"
        for note in self.notes:
            note_str = str(note).replace("\n", "\n\t")
            script += f"\n\t{note_str}"

        self.script += script + "\n"
