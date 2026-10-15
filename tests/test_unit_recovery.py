from dataclasses import replace

import numpy as np
import pytest

from src import erasure, unit_recovery as ur


def _file(n=300, seed=1, mean=200):
    rng = np.random.default_rng(seed)
    lines = []
    for i in range(n):
        pay = "".join(rng.choice(list("0123456789abcdef"), size=int(rng.integers(mean // 2, mean * 2))))
        lines.append(f"R{i:08d},{pay}\n")
    return "".join(lines).encode()


def _delete(data, drop):
    recs = ur._split_lines(data)
    return b"".join(r for i, r in enumerate(recs) if i not in drop), sum(len(recs[i]) for i in drop)


def test_rs_roundtrip():
    rng = np.random.default_rng(0)
    units = rng.integers(0, 256, size=(8, 64), dtype=np.uint8)
    par = erasure.encode(units, 3)
    erased = [1, 4, 6]
    surv = {j: units[j] for j in range(8) if j not in erased}
    dec = erasure.decode(surv, erased, par, 8, 64)
    for j in erased:
        assert np.array_equal(dec[j], units[j])


def test_rs_too_many_erasures():
    units = np.zeros((4, 8), dtype=np.uint8)
    par = erasure.encode(units, 1)
    with pytest.raises(ValueError):
        erasure.decode({}, [0, 1], par, 4, 8)


@pytest.mark.parametrize("scheme", [ur.RecordScheme(), ur.BlockScheme(256), ur.CDCScheme(256)])
def test_repair_after_scattered_deletion(scheme):
    data = _file()
    sk, pk = ur.new_keypair()
    prot = ur.protect(scheme, data, m=2, budget=0.4, sk=sk)
    assert prot is not None
    damaged, _ = _delete(data, {10, 120, 250})
    out, res = ur.repair(prot, damaged, pk, 1)
    assert res.success and out == data


@pytest.mark.parametrize("scheme", [ur.RecordScheme(), ur.BlockScheme(256), ur.CDCScheme(256)])
def test_fail_closed_when_erasures_exceed_parity(scheme):
    data = _file()
    sk, pk = ur.new_keypair()
    prot = ur.protect(scheme, data, m=1, budget=0.25, sk=sk)
    damaged, _ = _delete(data, set(range(0, 300, 3)))
    out, res = ur.repair(prot, damaged, pk, 1)
    assert out is None and not res.success


def test_tampered_parity_rejected():
    data = _file()
    sk, pk = ur.new_keypair()
    prot = ur.protect(ur.RecordScheme(), data, 2, 0.4, sk)
    damaged, _ = _delete(data, {5})
    bad = bytearray(prot.parity_blob)
    bad[0] ^= 1
    out, res = ur.repair(prot, damaged, pk, 1, parity_blob=bytes(bad))
    assert out is None and res.reason == "parity_tampered"


def test_rollback_and_forged_signature_rejected():
    data = _file()
    sk, pk = ur.new_keypair()
    prot = ur.protect(ur.RecordScheme(), data, 2, 0.4, sk, version=1)
    damaged, _ = _delete(data, {5})
    out, res = ur.repair(prot, damaged, pk, latest_version=2)
    assert out is None and res.reason == "stale_version"
    _, pk2 = ur.new_keypair()
    out, res = ur.repair(prot, damaged, pk2, 1)
    assert out is None and res.reason == "bad_signature"


@pytest.mark.parametrize("scheme", [ur.SortedRecordScheme(), ur.RecordGroupScheme(512)])
def test_new_schemes_repair(scheme):
    data = _file()
    sk, pk = ur.new_keypair()
    prot = ur.protect(scheme, data, m=2, budget=0.5, sk=sk)
    assert prot is not None
    damaged, _ = _delete(data, {10, 120, 250})
    out, res = ur.repair(prot, damaged, pk, 1)
    assert res.success and out == data


def test_sorted_stripes_reduce_padding():
    sk, _ = ur.new_keypair()
    rng = np.random.default_rng(3)
    lines = [f"R{i:08d}," + "x" * int(rng.lognormal(6, 1.2)) + "\n" for i in range(400)]
    data = "".join(lines).encode()
    a = ur.protect(ur.RecordScheme(), data, 2, 3.0, sk)
    b = ur.protect(ur.SortedRecordScheme(), data, 2, 3.0, sk)
    assert b.padded_bytes < a.padded_bytes


def test_cdc_sorted_repairs_and_pads_less():
    data = _file(n=400, mean=200)
    sk, pk = ur.new_keypair()
    a = ur.protect(ur.CDCScheme(256), data, 2, 0.8, sk)
    b = ur.protect(ur.CDCScheme(256, sort=True), data, 2, 0.8, sk)
    assert b.padded_bytes < a.padded_bytes
    damaged, _ = _delete(data, {7, 150, 333})
    out, res = ur.repair(b, damaged, pk, 1)
    assert res.success and out == data
    assert res.total_read_bytes >= res.repair_read_bytes + len(damaged)


def test_signed_manifest_rejects_shadow_version_and_parity_hash():
    data = _file(n=80)
    sk, pk = ur.new_keypair()
    prot = ur.protect(ur.RecordScheme(), data, 2, 0.8, sk, version=1)
    assert prot is not None

    forged_version = replace(prot.manifest, version=2)
    out, res = ur.repair(replace(prot, manifest=forged_version), data, pk, latest_version=2)
    assert out is None and res.reason == "manifest_inconsistent"

    bad_blob = bytearray(prot.parity_blob)
    bad_blob[0] ^= 1
    forged_hash = replace(prot.manifest, parity_hash=ur.sha(bytes(bad_blob)))
    out, res = ur.repair(
        replace(prot, manifest=forged_hash), data, pk, latest_version=1, parity_blob=bytes(bad_blob)
    )
    assert out is None and res.reason == "manifest_inconsistent"


def test_signed_manifest_rejects_shadow_table_and_commit():
    data = _file(n=80)
    sk, pk = ur.new_keypair()
    prot = ur.protect(ur.RecordScheme(), data, 2, 0.8, sk)
    assert prot is not None

    records = ur._split_lines(data)
    target = bytearray(records[3])
    target[-2] = ord("0") if target[-2] != ord("0") else ord("1")
    records[3] = bytes(target)
    damaged = b"".join(records)

    table = list(prot.manifest.table)
    uid, _length, _digest = table[3]
    table[3] = (uid, len(records[3]), ur.sha(records[3]))
    forged = replace(prot.manifest, table=tuple(table), commit=ur.sha(damaged))
    out, res = ur.repair(replace(prot, manifest=forged), damaged, pk, latest_version=1)
    assert out is None and res.reason == "manifest_inconsistent"


def test_signed_manifest_binds_scheme_and_layout_rule():
    data = _file(n=400, mean=200)
    sk, pk = ur.new_keypair()
    prot = ur.protect(ur.CDCScheme(256, sort=True), data, 2, 0.8, sk)
    assert prot is not None

    swapped = replace(prot, scheme=ur.CDCScheme(256, sort=False))
    out, res = ur.repair(swapped, data, pk, latest_version=1)
    assert out is None and res.reason == "bad_manifest"


def test_repair_uses_verified_parity_blob_not_mutable_cache():
    data = _file(n=120)
    sk, pk = ur.new_keypair()
    prot = ur.protect(ur.RecordScheme(), data, 2, 0.8, sk)
    assert prot is not None
    damaged, _ = _delete(data, {10, 90})

    prot.parity[0][0, 0] ^= 1
    out, res = ur.repair(prot, damaged, pk, latest_version=1)
    assert res.success and out == data
