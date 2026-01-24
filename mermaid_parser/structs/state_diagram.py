from typing import Optional, Union
from mermaid.statediagram import StateDiagram
from mermaid.statediagram.state import State, Start, End
from mermaid.statediagram.base import BaseTransition
from mermaid import Direction
from mermaid.configuration import Config


class HistoryState(State):
    """
    Represents a shallow history pseudo-state within a composite state.
    When a transition targets a history state, it resumes the last active
    substate of the parent composite state.
    """

    def __init__(self, parent_state_id: str) -> None:
        """
        Args:
            parent_state_id: The ID of the parent composite state this history belongs to
        """
        # Create an H pseudo-state with id like "ParentState_H"
        history_id = f"{parent_state_id}_H"
        super().__init__(id_=history_id, content="H")
        self.parent_state_id = parent_state_id
        self.is_history_state = True

    def __str__(self):
        return f"state {self.id_} <<history>>"


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
        root_initial_state: Optional[str] = None,
        initial_states: Optional[dict] = None,
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
            root_initial_state (Optional[str], optional): The root-level initial state ID. Defaults to None.
            initial_states (Optional[dict], optional): Map of composite state ID -> initial child state ID. Defaults to None.
        """  # noqa E501
        self.notes = notes
        self.root_initial_state = root_initial_state
        self.initial_states = initial_states if initial_states is not None else {}
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
