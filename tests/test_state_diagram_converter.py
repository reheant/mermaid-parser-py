import pytest
from mermaid_parser.converters.state_diagram import StateDiagramConverter
from mermaid_parser.structs.state_diagram import StateDiagramWithNote


class TestStateDiagramConverter:
    @pytest.fixture
    def converter(self):
        return StateDiagramConverter()

    def test_convert_state_diagram_with_notes(self, converter):
        """Test convert function with state diagram containing multiple notes"""
        mermaid_text = """
stateDiagram-v2
    State1: The state with a note
    [*] --> State1
    note right of State1
        note1
    end note
    note right of State1
        note2
    end note
    State1 --> State2
    note left of State2 : This is the note to the left.
    State2 --> [*]
        """

        result = converter.convert(mermaid_text)

        # Verify the result is a StateDiagramWithNote
        assert isinstance(result, StateDiagramWithNote)
        assert result.title == "State Diagram"
        assert result.version == "v2"

        # Verify states exist
        assert len(result.states) > 0
        state_ids = [getattr(state, "id_", None) for state in result.states]
        state_ids = [id_ for id_ in state_ids if id_ is not None]

        assert len(state_ids) == 4  # start, State1, State2, end

        # Check that our main states are present
        assert "State1" in state_ids
        assert "State2" in state_ids

        # Verify State1 has the correct description
        state1 = next(
            (
                state
                for state in result.states
                if getattr(state, "id_", None) == "State1"
            ),
            None,
        )
        assert state1 is not None
        assert state1.content == "The state with a note"

        # Verify transitions exist
        assert (
            len(result.transitions) >= 3
        )  # [*] -> State1, State1 -> State2, State2 -> [*]

        # Verify notes exist
        assert len(result.notes) == 3

        # Check note contents
        note_contents = [note.content for note in result.notes]
        assert "note1" in note_contents
        assert "note2" in note_contents
        assert "This is the note to the left." in note_contents

        # Verify note positions and targets
        state1_notes = [
            note for note in result.notes if note.target_state.id_ == "State1"
        ]
        state2_notes = [
            note for note in result.notes if note.target_state.id_ == "State2"
        ]

        assert len(state1_notes) == 2
        assert len(state2_notes) == 1

        # Check positions
        assert all([note.position == "right of" for note in state1_notes])
        assert state2_notes[0].position == "left of"

        expected_script = """---
title: State Diagram
---
stateDiagram-v2
    State1 : The state with a note
    State2 : State2
    [*] --> State1
    State1 --> State2
    State2 --> [*]
    note right of State1
        note1
    end note
    note right of State1
        note2
    end note
    note left of State2
        This is the note to the left.
    end note"""
        actual_script = result.script.strip()
        # replace tabs with spaces for comparision
        actual_script = actual_script.replace("\t", "    ")
        assert actual_script == expected_script.strip()
