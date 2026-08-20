'''Shared small .tar.gz archive fixtures for the archive test suite (decompress_xml_archive(),
xml_archive_import()).

Plain factory functions, not fixtures (consistent with sample_tables.py/xml_samples.py) - each
builds a fresh in-memory .tar.gz and returns its bytes.
'''

import io
import tarfile


def _build_tar_gz(members):
    '''members: dict[name] -> str content. Returns .tar.gz bytes with those members.'''
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode='w:gz') as tar:
        for name, content in members.items():
            data = content.encode('utf-8')
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def orders_archive_bytes():
    '''Two XML members with a repeating <Rec> element each (so record_path=None auto-detects
    correctly), one non-XML member to exercise the skip-with-warning filter, and one member
    nested in a subfolder to exercise member-name-as-dict-key path preservation.'''
    return _build_tar_gz({
        'a.xml': '<Root><Rec><X>1</X></Rec><Rec><X>11</X></Rec></Root>',
        'b.xml': '<Root><Rec><X>2</X><Y>9</Y></Rec></Root>',
        'readme.txt': 'not xml',
        'sub/c.xml': '<Root><Rec><X>3</X></Rec></Root>',
    })


def single_member_archive_bytes():
    '''One XML member, no non-XML members - the simplest case.'''
    return _build_tar_gz({'only.xml': '<Root><Rec><X>1</X></Rec></Root>'})


def no_xml_archive_bytes():
    '''An archive with no XML members at all - exercises the empty-result path.'''
    return _build_tar_gz({'readme.txt': 'not xml', 'data.csv': 'a,b\n1,2\n'})


def malformed_member_archive_bytes():
    '''One well-formed XML member and one malformed one - exercises on_malformed handling in
    bulk archive mode.'''
    return _build_tar_gz({
        'good.xml': '<Root><Rec><X>1</X></Rec></Root>',
        'bad.xml': '<root><a>1</a><b>2</root>',
    })
