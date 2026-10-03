"""Bounded uncompressed TFRecord framing with CRC32C; no TensorFlow runtime.

Payloads remain opaque. Compression, protobuf validity, source provenance and
causal observation boundaries belong to separate explicitly verified layers.
"""
import hashlib
import struct


def _table():
    values=[]
    for byte in range(256):
        value=byte
        for _ in range(8):
            value=(value>>1) ^ (0x82f63b78 if value&1 else 0)
        values.append(value)
    return tuple(values)


_TABLE=_table()


def crc32c(data):
    value=0xffffffff
    for byte in data:
        value=_TABLE[(value ^ byte)&255] ^ (value>>8)
    return value ^ 0xffffffff


def masked_crc32c(data):
    value=crc32c(data)
    return (((value>>15)|(value<<17))+0xa282ead8)&0xffffffff


def _read_exact(stream,size,*,allow_eof=False):
    chunks=[];remaining=size
    while remaining:
        chunk=stream.read(remaining)
        if not isinstance(chunk,bytes):raise ValueError('binary blocking stream required')
        if not chunk:
            if allow_eof and remaining==size:return None
            raise ValueError('truncated TFRecord frame')
        if len(chunk)>remaining:raise ValueError('stream returned excessive bytes')
        chunks.append(chunk);remaining-=len(chunk)
    return b''.join(chunks)


def read_records(stream,*,max_record_bytes):
    """Yield verified payload, zero-based frame index, byte offset and SHA-256.

    Clean EOF is permitted only between frames. Length integrity and the caller's
    positive byte cap are checked before attempting any payload allocation.
    A later bad frame raises; callers must not promote a partial file as complete.
    """
    if type(max_record_bytes) is not int or max_record_bytes<=0:
        raise ValueError('positive integer record byte cap required')
    offset=0;index=0
    while True:
        length_bytes=_read_exact(stream,8,allow_eof=True)
        if length_bytes is None:return
        length_crc=struct.unpack('<I',_read_exact(stream,4))[0]
        if length_crc!=masked_crc32c(length_bytes):raise ValueError('length CRC32C mismatch')
        length=struct.unpack('<Q',length_bytes)[0]
        if length>max_record_bytes:raise ValueError('record exceeds configured byte cap')
        payload=_read_exact(stream,length)
        payload_crc=struct.unpack('<I',_read_exact(stream,4))[0]
        if payload_crc!=masked_crc32c(payload):raise ValueError('payload CRC32C mismatch')
        yield {'index':index,'offset':offset,'payload':payload,'sha256':hashlib.sha256(payload).hexdigest()}
        index+=1;offset+=16+length
