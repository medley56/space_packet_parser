# XTCE Documentation on Variable Length Packets

The intent of this documentation is to describe the process of defining variable length packets in XTCE.

## Explanation
The PKT_LEN field is the length of the packet in bytes. 
PKT_LEN a) counts from zero and b) does not include the header bits. 
Hence, the length of the parameter in bits (PARAM_LEN) may be calculated by the following equation:

PARAM_LEN = 8*(PKT_LEN + 1) - FIXED_LENGTH_DATA

where FIXED_LENGTH_DATA is the sum of the length of each data field in bits. 

An example of this is shown below.

## Example
**Packet Definition:**  
"VERSION" : 3 bits  
"TYPE" : 1 bits  
"SEC_HDR_FLG" : 1 bits  
"PKT_APID" : 11 bits  
"SEQ_FLGS" : 2 bits  
"SRC_SEQ_CTR" : 14 bits  
"PKT_LEN" : 16 bits  
"SHCOARSE" : 32 bits  
"SID" : 8 bits  
"SPIN" : 8 bits  
"ABORTFLAG" : 1 bits  
"STARTDELAY" : 15 bits  
"COUNT" : 8 bits  
"EVENTDATA": variable length

FIXED_LENGTH_DATA = 32+8+8+1+15+8  

Therefore:  
EVENTDATA = 8 * (PKT_LEN + 1) - 72

This equation can be implemented in XTCE as follows:

```xml
<xtce:BinaryParameterType name="eventdata">
    <xtce:UnitSet/>
    <xtce:BinaryDataEncoding>
        <xtce:SizeInBits>
            <xtce:DynamicValue>
                <xtce:ParameterInstanceRef parameterRef="PKT_LEN"/>
                <xtce:LinearAdjustment intercept="-64" slope="8"/>
            </xtce:DynamicValue>
        </xtce:SizeInBits>
    </xtce:BinaryDataEncoding>
</xtce:BinaryParameterType>
```