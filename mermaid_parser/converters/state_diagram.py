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
        parent_id: str = None,
    ) -> tuple[dict[str, State], list[Note], list[Transition]]:
        """
        Extract and convert states, notes, and transitions from parsed state diagram data.

        Three-pass approach to correctly handle state hierarchy:
        1. First pass: Process state declarations (but not their nested content yet)
        2. Second pass: Process transitions at this level (now all states at this level are known)
        3. Third pass: Recursively process nested content of composite states

        Args:
            root_doc: List of parsed state diagram elements
            all_states: Dictionary to store all states by id
            parent_id: ID of the parent state (for nested states)

        Returns:
            Tuple of (states_dict, notes_list, transitions_list)
        """
        states = {}  # Dict to store states by id
        notes = []  # List to store notes
        transitions = []  # List to store transitions
        composite_states = []  # Track composite states for third pass

        # PASS 1: Process state declarations and notes (but don't recurse into composite states yet)
        for item in root_doc:
            if item["stmt"] == "state":
                state_id = item["id"]

                # Handle note items
                if "note" in item:
                    note_info = item["note"]
                    # Find or create the target state
                    if state_id not in states:
                        state = self._create_state(item, parent_id)
                        if state:
                            states[state_id] = state

                    note = Note(
                        content=note_info["text"],
                        target_state=states[state_id],
                        position=note_info["position"],
                    )
                    notes.append(note)
                else:
                    # Handle regular state items and composite states
                    if state_id not in all_states:
                        state = self._create_state(item, parent_id)
                        if state:
                            states[state_id] = state
                            all_states[state_id] = state

                            # If this is a composite state, save it for later processing
                            if "doc" in item:
                                composite_states.append((state_id, item["doc"]))
                    else:
                        # State already exists - just update description if provided
                        description = item.get("description", "")
                        if description and state_id in states:
                            states[state_id].content = description

        # PASS 2: Process transitions at this level
        level_transitions = self._convert_transitions(root_doc, states, all_states, parent_id)
        transitions.extend(level_transitions)

        # PASS 3: Now recursively process nested content of composite states
        for comp_state_id, comp_doc in composite_states:
            nested_states, nested_notes, nested_transitions = self._convert_states_and_notes(
                comp_doc, all_states, parent_id=comp_state_id
            )
            # Add nested states and their content
            states.update(nested_states)
            notes.extend(nested_notes)
            transitions.extend(nested_transitions)

        return states, notes, transitions

    def _create_state(self, state_info: dict, parent_id: str = None) -> State:
        """
        Create a State object from parsed state info.

        Args:
            state_info: Dictionary containing state information
            parent_id: ID of the parent state (if this is a nested state)

        Returns:
            State, Start, End, Composite, or Concurrent object
        """
        state_id = state_info["id"]
        if "_start" in state_id:
            return Start()
        elif "_end" in state_id:
            return End()
        else:
            # Create state (regular or composite)
            if "doc" in state_info:
                # Composite state - we'll create a regular state for now
                # The nested states will be processed separately
                state = Composite(
                    id_=state_id,
                    content=state_info.get("description", ""),
                    sub_states=[],  # Will be populated during recursive processing
                    transitions=[]
                )
            else:
                # Regular state
                state = State(id_=state_id, content=state_info.get("description", ""))

            state.id_ = state_id

            # Set parent_id if this state is nested
            if parent_id is not None:
                state.parent_id = parent_id

            return state

    def _convert_transitions(
        self,
        root_doc: list[dict],
        current_states: dict[str, State],
        all_states: dict[str, State],
        parent_id: str = None,
    ) -> list[Transition]:
        """
        Convert relation items to Transition objects.

        Args:
            root_doc: List of parsed state diagram elements
            current_states: Dictionary of current states on the current level
            all_states: Dictionary to store all states by id in the state diagram
            parent_id: ID of the parent state (for transitions within a composite state)

        Returns:
            List of Transition objects
        """
        transitions = []

        # Process relation items
        for item in root_doc:
            if item["stmt"] == "relation":
                state1_info = item["state1"]
                state2_info = item["state2"]

                # Handle state1
                from_id = state1_info["id"]
                if from_id not in all_states:
                    # This state is being defined for the first time
                    # Set parent_id if we're inside a composite state AND the state is not
                    # a self-reference or reference to a sibling at a different level
                    if parent_id and from_id == parent_id:
                        # Self-reference: Don't set parent_id
                        new_state = self._create_state(state1_info, parent_id=None)
                    elif "_start" in from_id or "_end" in from_id:
                        # Start/End states belong to the current scope
                        new_state = self._create_state(state1_info, parent_id)
                    elif parent_id:
                        # New state being defined in this scope
                        new_state = self._create_state(state1_info, parent_id)
                    else:
                        # Root level state
                        new_state = self._create_state(state1_info, parent_id=None)
                    all_states[from_id] = new_state
                    current_states[from_id] = new_state
                from_state = all_states[from_id]

                # Handle state2
                to_id = state2_info["id"]
                if to_id not in all_states:
                    # This state is being defined for the first time
                    if parent_id and to_id == parent_id:
                        # Self-reference: Don't set parent_id
                        new_state = self._create_state(state2_info, parent_id=None)
                    elif "_start" in to_id or "_end" in to_id:
                        # Start/End states belong to the current scope
                        new_state = self._create_state(state2_info, parent_id)
                    elif parent_id:
                        # New state being defined in this scope
                        new_state = self._create_state(state2_info, parent_id)
                    else:
                        # Root level state
                        new_state = self._create_state(state2_info, parent_id=None)
                    all_states[to_id] = new_state
                    current_states[to_id] = new_state
                to_state = all_states[to_id]

                # Get transition label if present
                label = item.get("description", "")

                transition = Transition(from_=from_state, to=to_state, label=label)
                transitions.append(transition)

        return transitions

    def _convert_state_diagram(
        self, root_doc: list[dict], all_states: dict[str, State]
    ) -> tuple[list[State], list[Transition], list[Note]]:
        """
        Convert parsed state diagram data to StateDiagramWithNote object.

        Args:
            root_doc: List of parsed state diagram elements
            all_states: Dictionary to store all states by id

        Returns:
            Tuple of (state_list, transitions, notes)
        """
        # Convert states, notes, and transitions (recursively processes composite states)
        states_dict, notes, transitions = self._convert_states_and_notes(root_doc, all_states)

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
