# Benchmarking Performance

## Full Packet Parsing Performance

Benchmarking packet parsing is challenging because performance is greatly impacted by the complexity of the packet 
structures being parsed. There are a few measures by which we can assess the performance of Space Packet Parser.

> [!NOTE]
> Throughout the Space Packet Parser repo and documentation space, 
> B/kB means bytes/kilobytes and b/kb means bits/kilobits.*

Common factors affecting performance:
- Presence of calibrators and context calibrators
- Complexity of container inheritance structure
- Number and size of fields in a packet
- Presence of large binary blobs (=high kbps, faster parsing)

### Packets Per Second

This is a metric we are often asked about. Unfortunately, the answer is that it depends on which packets are 
being parsed: how many fields are in each packet and how much extra work the parser is doing to sort out complex 
packet structures and evaluate calibrators.

### Kilobits Per Second

This metric is often used when discussing data volumes and downlink bandwidths to make sure that a data processing 
system can keep up with the data rate from a spacecraft in the time allowed for processing. This number is also 
affected by packet structures. It will be high for simple packets containing large binary blobs and low for 
complex packets containing many small fields.

### Results

These tests were run on an Apple Silicon M3 Max processor. 

As a baseline, for relatively simple packets (these are JPSS-1 spacecraft geolocation packets containing attitude 
and ephemeris data), we benchmarked using 7200 packets with a consistent size of 71B per packet. These packets contain 
32-bit floats and integers of various sizes.

- **26405-34620 packets per second**
- **14998-19664 kilobits per second**

Without progress printing (~13ms faster):
```
---------------------------------------------------------- benchmark: 1 tests ---------------------------------------------------------
Name (time in ms)                             Min       Max      Mean   StdDev    Median      IQR  Outliers     OPS  Rounds  Iterations
---------------------------------------------------------------------------------------------------------------------------------------
test_benchmark_simple_packet_parsing     195.3229  265.1687  230.5723  26.6511  235.8300  54.4324      10;0  4.3370      20           1
---------------------------------------------------------------------------------------------------------------------------------------

Legend:
  Outliers: 1 Standard Deviation from Mean; 1.5 IQR (InterQuartile Range) from 1st Quartile and 3rd Quartile.
  OPS: Operations Per Second, computed as 1 / Mean
```

With progress printing (showing progress output from Space Packet Parser):
```
---------------------------------------------------------- benchmark: 1 tests ---------------------------------------------------------
Name (time in ms)                             Min       Max      Mean   StdDev    Median      IQR  Outliers     OPS  Rounds  Iterations
---------------------------------------------------------------------------------------------------------------------------------------
test_benchmark_simple_packet_parsing     207.9945  272.7036  243.0210  16.8787  239.5151  20.2260       7;0  4.1149      20           1
---------------------------------------------------------------------------------------------------------------------------------------

Legend:
  Outliers: 1 Standard Deviation from Mean; 1.5 IQR (InterQuartile Range) from 1st Quartile and 3rd Quartile.
  OPS: Operations Per Second, computed as 1 / Mean
============================== 1 passed in 5.42s ===============================
Progress: [====================]100% [Elapsed: 0:00:00.234986, Parsed 511200 bytes (7200 packets) at 17403kb/s (30640pkts/s)]
Progress: [====================]100% [Elapsed: 0:00:00.238829, Parsed 511200 bytes (7200 packets) at 17123kb/s (30147pkts/s)]
Progress: [====================]100% [Elapsed: 0:00:00.272674, Parsed 511200 bytes (7200 packets) at 14998kb/s (26405pkts/s)]
Progress: [====================]100% [Elapsed: 0:00:00.217858, Parsed 511200 bytes (7200 packets) at 18771kb/s (33049pkts/s)]
Progress: [====================]100% [Elapsed: 0:00:00.266889, Parsed 511200 bytes (7200 packets) at 15323kb/s (26977pkts/s)]
Progress: [====================]100% [Elapsed: 0:00:00.242260, Parsed 511200 bytes (7200 packets) at 16881kb/s (29720pkts/s)]
Progress: [====================]100% [Elapsed: 0:00:00.240147, Parsed 511200 bytes (7200 packets) at 17029kb/s (29981pkts/s)]
Progress: [====================]100% [Elapsed: 0:00:00.249718, Parsed 511200 bytes (7200 packets) at 16376kb/s (28832pkts/s)]
Progress: [====================]100% [Elapsed: 0:00:00.238504, Parsed 511200 bytes (7200 packets) at 17146kb/s (30188pkts/s)]
Progress: [====================]100% [Elapsed: 0:00:00.207969, Parsed 511200 bytes (7200 packets) at 19664kb/s (34620pkts/s)]
Progress: [====================]100% [Elapsed: 0:00:00.271132, Parsed 511200 bytes (7200 packets) at 15083kb/s (26555pkts/s)]
Progress: [====================]100% [Elapsed: 0:00:00.240643, Parsed 511200 bytes (7200 packets) at 16994kb/s (29919pkts/s)]
Progress: [====================]100% [Elapsed: 0:00:00.237156, Parsed 511200 bytes (7200 packets) at 17244kb/s (30359pkts/s)]
Progress: [====================]100% [Elapsed: 0:00:00.231368, Parsed 511200 bytes (7200 packets) at 17675kb/s (31119pkts/s)]
Progress: [====================]100% [Elapsed: 0:00:00.232334, Parsed 511200 bytes (7200 packets) at 17602kb/s (30989pkts/s)]
Progress: [====================]100% [Elapsed: 0:00:00.260499, Parsed 511200 bytes (7200 packets) at 15699kb/s (27639pkts/s)]
Progress: [====================]100% [Elapsed: 0:00:00.240519, Parsed 511200 bytes (7200 packets) at 17003kb/s (29935pkts/s)]
Progress: [====================]100% [Elapsed: 0:00:00.235573, Parsed 511200 bytes (7200 packets) at 17360kb/s (30563pkts/s)]
Progress: [====================]100% [Elapsed: 0:00:00.237279, Parsed 511200 bytes (7200 packets) at 17235kb/s (30344pkts/s)]
Progress: [====================]100% [Elapsed: 0:00:00.234196, Parsed 511200 bytes (7200 packets) at 17462kb/s (30743pkts/s)]
Progress: [====================]100% [Elapsed: 0:00:00.264275, Parsed 511200 bytes (7200 packets) at 15474kb/s (27244pkts/s)]
```

## Parsing Individual Values Benchmarking

In addition to the benchmarks discussed above, we also benchmarked the low level operations that make up most 
of the parsing work. The parser relies on two fundamental methods: `read_as_int(nbits)` and `read_as_bytes(nbits)`,
each of which is capable of reading an arbitrary number of bits from a byte string. That is, the binary data being 
parsed need not be byte aligned or even an integer number of bytes.

```
-------------------------------------------------------------------------------------------------------- benchmark: 5 tests --------------------------------------------------------------------------------------------------------
Name (time in ns)                                              Min                 Max                Mean             StdDev              Median                IQR            Outliers  OPS (Mops/s)            Rounds  Iterations
------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
test_benchmark__read_as_bytes__aligned                    231.4160 (1.0)      237.2910 (1.0)      234.8330 (1.0)       3.0527 (1.0)      235.7920 (1.0)       4.4063 (1.0)           1;0        4.2583 (1.0)           3        1000
test_benchmark__read_as_int__aligned                      253.0000 (1.09)     302.1660 (1.27)     273.4720 (1.16)     25.5934 (8.38)     265.2500 (1.12)     36.8745 (8.37)          1;0        3.6567 (0.86)          3        1000
test_benchmark__read_as_int__non_aligned                  361.6250 (1.56)     379.7910 (1.60)     371.4720 (1.58)      9.1789 (3.01)     373.0000 (1.58)     13.6245 (3.09)          1;0        2.6920 (0.63)          3        1000
test_benchmark__read_as_bytes__non_aligned_full_bytes     417.5420 (1.80)     439.2500 (1.85)     425.0833 (1.81)     12.2772 (4.02)     418.4580 (1.77)     16.2810 (3.69)          1;0        2.3525 (0.55)          3        1000
test_benchmark__read_as_bytes__partial_bytes              441.6660 (1.91)     460.8340 (1.94)     452.3473 (1.93)      9.7707 (3.20)     454.5420 (1.93)     14.3760 (3.26)          1;0        2.2107 (0.52)          3        1000
------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
```

The results are as expected:

- The most efficient parsing is byte-aligned parsing of objects that are integer number of bytes in length. 
- Parsing integers is slower than raw bytes due to the conversion from bytes to int.
- The most expensive operation is parsing a bytes object that is an odd number of bits (e.g. 6 bits). This is due 
  to the padding operation required to return a bytes object from such a call.
- The only surprise is that non-aligned integers parse faster than non-aligned full bytes. Ironically this is due
  to a check that we perform during byte parsing to return faster if the request _is_ byte aligned.
