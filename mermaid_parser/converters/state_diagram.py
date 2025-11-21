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
        parent_path: str = None,
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
            parent_id: ID of the parent state (for nested states) - this is the simple parent, e.g. 'Print'
            parent_path: Full hierarchical path to parent, e.g. 'On_LoggedIn_Print' - used for scoped keys

        Returns:
            Tuple of (states_dict, notes_list, transitions_list)
        """
        # If parent_path is not provided, use parent_id
        if parent_path is None:
            parent_path = parent_id
        states = {}  # Dict to store states by id
        notes = []  # List to store notes
        transitions = []  # List to store transitions
        composite_states = []  # Track composite states for third pass

        # PASS 1: Process state declarations and notes (but don't recurse into composite states yet)
        for item in root_doc:
            if item["stmt"] == "state":
                state_id = item["id"]
                scoped_key = self._get_scoped_key(state_id, parent_path)

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
                    if scoped_key not in all_states:
                        state = self._create_state(item, parent_id)
                        if state:
                            states[state_id] = state
                            all_states[scoped_key] = state

                            # If this is a composite state, save it for later processing
                            if "doc" in item:
                                composite_states.append((state_id, item["doc"]))
                    else:
                        # State already exists - just update description if provided
                        description = item.get("description", "")
                        if description and state_id in states:
                            states[state_id].content = description

        # PASS 2: Recursively process nested content FIRST if we're at root level
        # This ensures deeply nested states exist before root tries to reference them
        # For non-root levels, process transitions first (breadth-first within nested scopes)
        if parent_id is None:
            # Root level: process nested scopes first
            for comp_state_id, comp_doc in composite_states:
                new_parent_path = f"{parent_path}_{comp_state_id}" if parent_path else comp_state_id
                nested_states, nested_notes, nested_transitions = self._convert_states_and_notes(
                    comp_doc, all_states, parent_id=comp_state_id, parent_path=new_parent_path
                )
                states.update(nested_states)
                notes.extend(nested_notes)
                transitions.extend(nested_transitions)

            # Then process root-level transitions
            level_transitions = self._convert_transitions(root_doc, states, all_states, parent_id, parent_path)
            transitions.extend(level_transitions)
        else:
            # Non-root level: process transitions first (breadth-first)
            level_transitions = self._convert_transitions(root_doc, states, all_states, parent_id, parent_path)
            transitions.extend(level_transitions)

            # Then recursively process nested content
            for comp_state_id, comp_doc in composite_states:
                new_parent_path = f"{parent_path}_{comp_state_id}" if parent_path else comp_state_id
                nested_states, nested_notes, nested_transitions = self._convert_states_and_notes(
                    comp_doc, all_states, parent_id=comp_state_id, parent_path=new_parent_path
                )
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

    def _get_scoped_key(self, state_id: str, parent_id: str = None) -> str:
        """
        Generate a scoped key for a state based on its ID and parent context.
        This allows multiple states with the same name in different scopes.

        Args:
            state_id: The state's ID
            parent_id: The parent state's ID (if nested)

        Returns:
            A scoped key for the state
        """
        if parent_id and not ("_start" in state_id or "_end" in state_id):
            return f"{parent_id}_{state_id}"
        return state_id

    def _find_state_in_all_states(self, state_id: str, parent_path: str, all_states: dict[str, State]) -> tuple[State, str]:
        """
        Find a state in all_states, checking both scoped and unscoped keys.
        Priority:
        1. Exact scoped key (within current context) - for states defined in this scope
        2. Unscoped key (global/root) - for states defined at root level
        3. Parent scope - for states defined in parent composite state
        4. Any scope - for cross-scope references (only when searching from root)

        Note: Within a scope, we DO NOT search sibling scopes - each scope can have its own state with the same name.
              But from root level, we search all scopes.

        Args:
            state_id: The state's ID
            parent_path: The current parent path (hierarchical path for scoping)
            all_states: Dictionary of all states

        Returns:
            Tuple of (state, key_used) or (None, None) if not found
        """
        # First check if it exists in the current scope with a scoped key
        scoped_key = self._get_scoped_key(state_id, parent_path)
        if scoped_key in all_states:
            return all_states[scoped_key], scoped_key

        # Then check if it exists at unscoped (global/root) level
        # This handles references to root-level states from any scope
        if state_id in all_states:
            return all_states[state_id], state_id

        # Check parent scopes by walking up the hierarchy
        # e.g., if we're in On_LoggedIn_Print and looking for Idle,
        # check if On_LoggedIn_Idle exists
        if parent_path and '_' in parent_path:
            parts = parent_path.split('_')
            for i in range(len(parts), 0, -1):
                parent_prefix = '_'.join(parts[:i])
                parent_scoped_key = f"{parent_prefix}_{state_id}"
                if parent_scoped_key in all_states:
                    return all_states[parent_scoped_key], parent_scoped_key

        # If we're at root level (parent_path is None), search all scopes for this state
        # This handles cases where a state is defined in a nested scope but referenced from root
        if parent_path is None:
            for key, state in all_states.items():
                # Check if this key ends with the state_id and the state's id_ matches
                if (key.endswith(f"_{state_id}") or key == state_id) and hasattr(state, 'id_') and state.id_ == state_id:
                    return state, key

        return None, None

    def _convert_transitions(
        self,
        root_doc: list[dict],
        current_states: dict[str, State],
        all_states: dict[str, State],
        parent_id: str = None,
        parent_path: str = None,
    ) -> list[Transition]:
        """
        Convert relation items to Transition objects.

        Args:
            root_doc: List of parsed state diagram elements
            current_states: Dictionary of current states on the current level
            all_states: Dictionary to store all states by id in the state diagram
            parent_id: ID of the parent state (for transitions within a composite state)
            parent_path: Full hierarchical path to parent - used for scoped keys

        Returns:
            List of Transition objects
        """
        # If parent_path is not provided, use parent_id
        if parent_path is None:
            parent_path = parent_id
        transitions = []

        # Process relation items
        for item in root_doc:
            if item["stmt"] == "relation":
                state1_info = item["state1"]
                state2_info = item["state2"]

                # Handle state1
                from_id = state1_info["id"]
                from_state, found_key = self._find_state_in_all_states(from_id, parent_path, all_states)

                # If we're at root level and found a state in a nested scope that's the SOURCE of this transition
                # then promote it to root level (it's directly accessible from root)
                if from_state and parent_id is None and found_key and '_' in found_key:
                    # This state is the source of a root-level transition
                    # Promote it to root level
                    from_state.parent_id = None
                    # Also store it with unscoped key for future lookups
                    all_states[from_id] = from_state

                if from_state is None:
                    # This state is being defined for the first time
                    if parent_id and from_id == parent_id:
                        # Self-reference: Don't set parent_id, use unscoped key
                        new_state = self._create_state(state1_info, parent_id=None)
                        all_states[from_id] = new_state
                        from_state = new_state
                    elif "_start" in from_id or "_end" in from_id:
                        # Start/End states: use scoped key
                        scoped_key = self._get_scoped_key(from_id, parent_path)
                        new_state = self._create_state(state1_info, parent_id)
                        all_states[scoped_key] = new_state
                        from_state = new_state
                    elif parent_id:
                        # New state in this scope: use scoped key
                        scoped_key = self._get_scoped_key(from_id, parent_path)
                        new_state = self._create_state(state1_info, parent_id)
                        all_states[scoped_key] = new_state
                        from_state = new_state
                    else:
                        # Root level state: use unscoped key
                        new_state = self._create_state(state1_info, parent_id=None)
                        all_states[from_id] = new_state
                        from_state = new_state

                    if from_id in current_states:
                        current_states[from_id] = from_state

                # Handle state2
                to_id = state2_info["id"]
                to_state, found_key = self._find_state_in_all_states(to_id, parent_path, all_states)

                if to_state is None:
                    # This state is being defined for the first time
                    if parent_id and to_id == parent_id:
                        # Self-reference: Don't set parent_id, use unscoped key
                        new_state = self._create_state(state2_info, parent_id=None)
                        all_states[to_id] = new_state
                        to_state = new_state
                    elif "_start" in to_id or "_end" in to_id:
                        # Start/End states: use scoped key
                        scoped_key = self._get_scoped_key(to_id, parent_path)
                        new_state = self._create_state(state2_info, parent_id)
                        all_states[scoped_key] = new_state
                        to_state = new_state
                    elif parent_id:
                        # New state in this scope: use scoped key
                        scoped_key = self._get_scoped_key(to_id, parent_path)
                        new_state = self._create_state(state2_info, parent_id)
                        all_states[scoped_key] = new_state
                        to_state = new_state
                    else:
                        # Root level state: use unscoped key
                        new_state = self._create_state(state2_info, parent_id=None)
                        all_states[to_id] = new_state
                        to_state = new_state

                    if to_id in current_states:
                        current_states[to_id] = to_state

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

        # Create the state diagram from all_states (which includes both scoped and unscoped states)
        state_list = list(all_states.values())

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
