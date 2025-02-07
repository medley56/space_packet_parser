"""Fast benchmarks"""
import pytest

from space_packet_parser import packets

@pytest.mark.benchmark
def test_benchmark__read_as_int__aligned(benchmark):
    """Benchmark performance of reading byte-aligned ints from a bytes object

    This test essentially makes a packet with a long user data section of alternating ones and zeros
    """
    rounds = 3
    warmup_rounds = 1
    test_byte = b'\x55'  # 01 01 01 01
    n_iterations = 1000
    nbits = 16
    expected_value = 21845  # 01010101 01010101
    n_test_byte_repeats = ((rounds + warmup_rounds) * n_iterations * nbits // 8) + 1
    raw_packet = packets.create_ccsds_packet(data=test_byte * n_test_byte_repeats)
    # parse the header to move the bit cursor
    _ = raw_packet.header_values

    value = benchmark.pedantic(raw_packet.read_as_int, args=(nbits, ),
                               rounds=rounds,
                               iterations=n_iterations,
                               warmup_rounds=warmup_rounds)

    assert value == expected_value


@pytest.mark.benchmark
def test_benchmark__read_as_int__non_aligned(benchmark):
    """Benchmark performance of reading non-byte-aligned ints from a bytes object

    This test essentially makes a packet with a long user data section of alternating ones and zeros
    """
    rounds = 3
    warmup_rounds = 1
    test_byte = b'\x55'  # 01 01 01 01
    n_iterations = 1000
    nbits = 18
    expected_value = 87381 # 01010101 01010101 01
    n_test_byte_repeats = ((rounds + warmup_rounds) * n_iterations * nbits // 8) + 1
    raw_packet = packets.create_ccsds_packet(data=test_byte * n_test_byte_repeats)
    # parse the header to move the bit cursor
    _ = raw_packet.header_values

    value = benchmark.pedantic(raw_packet.read_as_int, args=(nbits, ),
                               rounds=rounds,
                               iterations=n_iterations,
                               warmup_rounds=warmup_rounds)

    assert value == expected_value


@pytest.mark.benchmark
def test_benchmark__read_as_bytes__aligned(benchmark):
    """Benchmark performance of reading full, aligned, bytes from a bytes object

    This test essentially makes a packet with a long user data section of alternating ones and zeros
    """
    rounds = 3
    warmup_rounds = 1
    test_byte = b'\x55'  # 01 01 01 01
    n_iterations = 1000
    nbits = 16
    expected_value = b'\x55\x55'  # 01010101 01010101
    n_test_byte_repeats = ((rounds + warmup_rounds) * n_iterations * nbits // 8) + 1
    raw_packet = packets.create_ccsds_packet(data=test_byte * n_test_byte_repeats)
    # parse the header to move the bit cursor
    _ = raw_packet.header_values

    value = benchmark.pedantic(raw_packet.read_as_bytes, args=(nbits, ),
                               rounds=rounds,
                               iterations=n_iterations,
                               warmup_rounds=warmup_rounds)

    assert value == expected_value


@pytest.mark.benchmark
def test_benchmark__read_as_bytes__non_aligned_full_bytes(benchmark):
    """Benchmark performance of reading full bytes, not-byte-aligned (offset by 1 bit), from a bytes object

    This test essentially makes a packet with a long user data section of alternating ones and zeros
    """
    rounds = 3
    warmup_rounds = 1
    test_byte = b'\x55'  # 01 01 01 01
    n_iterations = 1000
    nbits = 16
    expected_value = b'\xaa\xaa'  # 10101010 10101010
    n_test_byte_repeats = ((rounds + warmup_rounds) * n_iterations * nbits // 8) + 1
    raw_packet = packets.create_ccsds_packet(data=test_byte * n_test_byte_repeats)
    raw_packet.pos += 1  # Move cursor to non-aligned position
    # parse the header to move the bit cursor
    _ = raw_packet.header_values

    value = benchmark.pedantic(raw_packet.read_as_bytes, args=(nbits, ),
                               rounds=rounds,
                               iterations=n_iterations,
                               warmup_rounds=warmup_rounds)

    assert value == expected_value


@pytest.mark.benchmark
def test_benchmark__read_as_bytes__partial_bytes(benchmark):
    """Benchmark performance of reading partial bytes from a bytes object, resulting
    in padded values.

    This test essentially makes a packet with a long user data section of alternating ones and zeros
    """
    rounds = 3
    warmup_rounds = 1
    test_byte = b'\x55'  # 01 01 01 01
    n_iterations = 1000
    nbits = 6
    expected_value = b'\x15'  # 00 01 01 01 (MSB padded with 2 bits)
    n_test_byte_repeats = ((rounds + warmup_rounds) * n_iterations * nbits // 8) + 1
    raw_packet = packets.create_ccsds_packet(data=test_byte * n_test_byte_repeats)

    # parse the header to move the bit cursor
    _ = raw_packet.header_values

    value = benchmark.pedantic(raw_packet.read_as_bytes, args=(nbits, ),
                               rounds=rounds,
                               iterations=n_iterations,
                               warmup_rounds=warmup_rounds)

    assert value == expected_value
