from contracts.constitutional_path import validate_authoritative_history, validate_history, _record_digest


def t(i, source, target, parent, **extra):
    d={"transition_id":f"T{i}","sequence":i,"parent_digest":parent,"from":source,"to":target}
    d.update(extra)
    return d


def test_incomplete_prefix_is_not_authoritative_even_if_constitutionally_valid():
    states=[
        {"active_generation":"G1","generations":{"G1":"ACTIVE"}},
        {"active_generation":"G2","generations":{"G1":"RETIRED","G2":"ACTIVE"}},
    ]
    transitions=[t(0,"G1","G2","GENESIS")]
    assert validate_history(states, transitions).constitutional_valid
    r=validate_authoritative_history(states, transitions, history_complete=False)
    assert not r.authoritative_valid


def test_reordering_is_detected_by_sequence_and_lineage():
    a=t(0,"G1","G2","GENESIS")
    b=t(1,"G2","G3","")
    b["parent_digest"]="PLACEHOLDER"
    # Even if an attacker supplies a self-consistent-looking reorder, the
    # explicit sequence numbers identify the original positions.
    r=validate_authoritative_history([{}, {}, {}],[b,a],history_complete=True)
    assert not r.sequence_valid
    assert not r.lineage_valid
    assert not r.authoritative_valid


def test_duplicate_transition_id_reveals_selective_or_replayed_history():
    a=t(0,"G1","G2","GENESIS")
    digest=__import__('hashlib').sha256(__import__('json').dumps(a,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    b=t(1,"G2","G3",digest)
    duplicate=dict(b, transition_id="T0")
    r=validate_authoritative_history([{}, {}, {}],[a,duplicate],history_complete=True,expected_terminal="T1")
    assert not r.uniqueness_valid
    assert not r.authoritative_valid


def test_forked_branch_cannot_claim_the_same_parent_without_distinct_lineage_anchor():
    a=t(0,"G1","G2","GENESIS")
    digest=__import__('hashlib').sha256(__import__('json').dumps(a,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    branch_a=t(1,"G2","G3",digest)
    branch_b=t(1,"G2","G4",digest)
    # Each branch may be internally valid, but a presented history containing
    # both as one linear sequence is not valid because sequence/lineage break.
    r=validate_authoritative_history([{}, {}, {}, {}],[a,branch_a,branch_b],history_complete=True,expected_terminal="T1")
    assert not r.sequence_valid
    assert not r.lineage_valid
    assert not r.authoritative_valid


def test_terminal_anchor_rejects_a_valid_but_truncated_prefix():
    a=t(0,"G1","G2","GENESIS")
    digest=__import__('hashlib').sha256(__import__('json').dumps(a,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    b=t(1,"G2","G3",digest)
    r=validate_authoritative_history([{}, {}, {}],[a],history_complete=True,expected_terminal="T1")
    assert not r.anchored
    assert not r.authoritative_valid


def test_complete_linear_history_can_pass_authority_boundary():
    a=t(0,"G1","G2","GENESIS")
    digest=__import__('hashlib').sha256(__import__('json').dumps(a,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    b=t(1,"G2","G3",digest)
    r=validate_authoritative_history([{}, {}, {}],[a,b],history_complete=True,expected_terminal="T1",expected_terminal_digest=_record_digest(b))
    assert r.authoritative_valid


def test_terminal_identifier_alone_cannot_authorize_modified_terminal_contents():
    a=t(0,"G1","G2","GENESIS")
    digest=__import__('hashlib').sha256(__import__('json').dumps(a,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    b=t(1,"G2","G3",digest)
    anchor=_record_digest(b)
    altered=dict(b, to="G4")
    r=validate_authoritative_history([{}, {}, {}],[a,altered],history_complete=True,expected_terminal="T1",expected_terminal_digest=anchor)
    assert not r.anchored
    assert not r.authoritative_valid


def test_terminal_anchor_digest_binds_the_exact_terminal_record():
    a=t(0,"G1","G2","GENESIS")
    digest=__import__('hashlib').sha256(__import__('json').dumps(a,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    b=t(1,"G2","G3",digest)
    r=validate_authoritative_history([{}, {}, {}],[a,b],history_complete=True,expected_terminal_digest=_record_digest(b))
    assert r.authoritative_valid


def test_authoritative_validation_rejects_state_transition_cardinality_mismatch():
    a=t(0,"G1","G2","GENESIS")
    r=validate_authoritative_history([{}],[a],history_complete=True,expected_terminal_digest=_record_digest(a))
    assert not r.sequence_valid
    assert not r.authoritative_valid
