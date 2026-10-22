"""MurmurHash64A as verified against the old resource validator."""
import struct

MASK=(1<<64)-1
MULTIPLIER=0xc6a4a7935bd1e995
INVERSE=pow(MULTIPLIER,-1,1<<64)
SEED=0xdeadbeefabad1dea

def mix(value):
    value=value*MULTIPLIER&MASK
    value^=value>>47
    return value*MULTIPLIER&MASK

def unshift(value):
    return value^(value>>47)

def unmix(value):
    return unshift(value*INVERSE&MASK)*INVERSE&MASK

def state(data,seed=SEED):
    h=(seed^len(data)*MULTIPLIER)&MASK
    for offset in range(0,len(data)//8*8,8):
        h=(h^mix(struct.unpack_from('<Q',data,offset)[0]))*MULTIPLIER&MASK
    tail=data[len(data)//8*8:]
    if tail:h=(h^int.from_bytes(tail,'little'))*MULTIPLIER&MASK
    return h

def murmur64(data,seed=SEED):
    h=state(data,seed);h=unshift(h);h=h*MULTIPLIER&MASK
    return unshift(h)

def padding_word_for_hash(data,word_offset,wanted,seed=SEED):
    """Solve one aligned eight-byte word, leaving all other bytes fixed."""
    if word_offset%8 or not 0<=word_offset<=len(data)//8*8-8:
        raise ValueError('Correction word must be aligned and fully in data')
    after=unshift(unshift(wanted)*INVERSE&MASK)
    tail=data[len(data)//8*8:]
    if tail:after=(after*INVERSE&MASK)^int.from_bytes(tail,'little')
    for offset in range(len(data)//8*8-8,word_offset,-8):
        after=(after*INVERSE&MASK)^mix(struct.unpack_from('<Q',data,offset)[0])
    before=(seed^len(data)*MULTIPLIER)&MASK
    for offset in range(0,word_offset,8):
        before=(before^mix(struct.unpack_from('<Q',data,offset)[0]))*MULTIPLIER&MASK
    return struct.pack('<Q',unmix(before^(after*INVERSE&MASK)))


if __name__=='__main__':
    import argparse
    from pathlib import Path
    parser=argparse.ArgumentParser(description='Print MurmurHash64A of a local file; no modifications.')
    parser.add_argument('input',type=Path)
    parser.add_argument('--seed',type=lambda value:int(value,0),default=SEED)
    args=parser.parse_args()
    try:print('%016X'%murmur64(args.input.read_bytes(),args.seed))
    except OSError as error:parser.exit(2,str(error)+'\n')
