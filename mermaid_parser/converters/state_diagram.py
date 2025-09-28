from loguru import logger
from mermaid_parser.structs.state_diagram import StateDiagramWithNote, Note
from mermaid.statediagram.state import Composite, Concurrent, End, Start, State
from mermaid.statediagram.transition import Choice, Fork, Join, Transition
from mermaid_parser import MermaidParser
import networkx as nx

"""
Currently, this class gives basic support for converting flat state diagrams with notes.
Under construction

# TODO: Add support for Composite and Concurrent states
# TODO: Add support for Fork and Join transitions
# TODO: Add support for Choice transitions
# TODO: Add support for converting to networkx graph
"""


class StateDiagramConverter:
    def __init__(self):
        self.parser = MermaidParser()

    def convert(self, mermaid_text: str) -> StateDiagramWithNote:
        # TODO: the current parser does not handle rendering styles
        parsed_data = self.parser.parse(mermaid_text)
        graph_type = parsed_data.get("graph_type")
        if "stateDiagram" not in graph_type:
            raise ValueError(f"Unsupported graph type: {graph_type}")

        all_states = {}
        states, transitions, notes = self._convert_state_diagram(
            parsed_data["graph_data"]["rootDoc"], all_states
        )
        return StateDiagramWithNote(
            title="State Diagram",
            states=states,
            transitions=transitions,
            notes=notes,
            version="v2",
        )

    def _convert_states_and_notes(
        self,
        root_doc: list[dict],
        all_states: dict[str, State],
    ) -> tuple[dict[str, State], list[Note]]:
        """
        Extract and convert states and notes from parsed state diagram data.

        Args:
            root_doc: List of parsed state diagram elements
            all_states: Dictionary to store all states by id

        Returns:
            Tuple of (states_dict, notes_list)
        """
        states = {}  # Dict to store states by id
        notes = []  # List to store notes

        # Process all state items
        for item in root_doc:
            if item["stmt"] == "state":
                state_id = item["id"]

                # Handle note items
                if "note" in item:
                    note_info = item["note"]
                    # Find or create the target state
                    if state_id not in states:
                        states[state_id] = self._create_state(item)

                    note = Note(
                        content=note_info["text"],
                        target_state=states[state_id],
                        position=note_info["position"],
                    )
                    notes.append(note)
                else:
                    # Handle regular state items
                    if state_id not in states:
                        states[state_id] = self._create_state(item)
                        all_states[state_id] = states[state_id]
                    else:
                        # Update existing state with description if provided
                        description = item.get("description", "")
                        if description:
                            states[state_id].content = description

        return states, notes

    def _create_state(self, state_info: dict) -> State:
        state_id = state_info["id"]
        if "_start" in state_id:
            return Start()
        elif "_end" in state_id:
            return End()
        elif "doc" not in state_info:
            # regular state
            state = State(id_=state_id, content=state_info.get("description", ""))
            state.id_ = state_id
            return state

    def _convert_transitions(
        self,
        root_doc: list[dict],
        current_states: dict[str, State],
        all_states: dict[str, State],
    ) -> list[Transition]:
        """
        Convert relation items to Transition objects.

        Args:
            root_doc: List of parsed state diagram elements
            current_states: Dictionary of current states on the current level
            all_states: Dictionary to store all states by id in the state diagram

        Returns:
            List of Transition objects
        """
        transitions = []

        # Process relation items
        for item in root_doc:
            if item["stmt"] == "relation":
                state1_info = item["state1"]
                state2_info = item["state2"]

                # Handle start and end states for state1
                from_id = state1_info["id"]
                if from_id not in all_states:
                    all_states[from_id] = self._create_state(state1_info)
                    current_states[from_id] = all_states[from_id]
                from_state = all_states[from_id]

                # Handle start and end states for state2
                to_id = state2_info["id"]
                if to_id not in all_states:
                    all_states[to_id] = self._create_state(state2_info)
                    current_states[to_id] = all_states[to_id]
                to_state = all_states[to_id]

                # Get transition label if present
                label = item.get("description", "")

                transition = Transition(from_=from_state, to=to_state, label=label)
                transitions.append(transition)

        return transitions

    def _convert_state_diagram(
        self, root_doc: list[dict], all_states: dict[str, State]
    ) -> StateDiagramWithNote:
        """
        Convert parsed state diagram data to StateDiagramWithNote object.

        Args:
            root_doc: List of parsed state diagram elements
            all_states: Dictionary to store all states by id

        Returns:
            StateDiagramWithNote object
        """
        # Convert states and notes
        states_dict, notes = self._convert_states_and_notes(root_doc, all_states)

        # Convert transitions
        transitions = self._convert_transitions(root_doc, states_dict, all_states)

        # Create the state diagram
        state_list = list(states_dict.values())

        return state_list, transitions, notes

    # def to_networkx(self, state_diagram: StateDiagram) -> nx.DiGraph:
    #     G = nx.DiGraph()
    #     for node in state_diagram.nodes.values():
    #         G.add_node(node.id, content=node.content, shape=node.shape)
    #     for link in state_diagram.links:
    #         G.add_edge(
    #             link.origin.id, link.end.id, shape=link.shape, message=link.message
    #         )
    #     return G
