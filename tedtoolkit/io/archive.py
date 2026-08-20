'''tedtoolkit.io.archive - .tar.gz/.tgz archive handling for bundles of XML files. No archive
*export* is provided here - only extraction/import, mirroring tedtoolkit.io.xml's import-only
stance.

Two independent capabilities, both stdlib `tarfile`-backed (no new dependency):
- `decompress_xml_archive()` - extract every member of an archive to a folder on disk, as-is
  (no XML filtering - "decompress" here means the whole archive, not just its XML members).
- `xml_archive_import()` - parse and flatten every *.xml* member inside an archive into a
  list-of-lists table (skipping non-XML members with a warning), returning
  dict[member_name] -> table. This reuses tedtoolkit.io.xml's flattening engine directly:
  `_resolve_flatten_kwargs()` for the curated-prompt/silent-default kwarg resolution, and
  `_xml_import_bulk_core_from_sources()` for the actual "many named XML sources -> one dict of
  tables" engine (including column_order='stable' cross-item column unification) - both were
  factored out of xml.py specifically to support this module without duplicating that logic.
  Each archive member is read fully into memory as bytes, one member at a time (not the whole
  archive at once), before flattening - see xml_archive_import()'s own docstring for why.
'''

import io
import os
import tarfile

import click

from tedtoolkit.history import _add_kwarg_to_last_command, _check_assignment, _quoted
from tedtoolkit.gui.dialogs import g_sel_file, g_sel_folder
from tedtoolkit.io.xml import (_resolve_flatten_kwargs, _make_flatten_opts,
                               _xml_import_bulk_core_from_sources)

ARCHIVE_FILETYPES = [('Archives', ('*.tar.gz', '*.tgz')), ('All files', ('*.*'))]


def _open_archive(archive_path):
    '''Open archive_path (path/Path/raw bytes/file-like) for reading via stdlib tarfile.
    mode='r:*' auto-detects gzip/bz2/xz/no compression, so a plain .tar also works as a free
    side effect of using the correct stdlib call - extension auto-detection in data_import() is
    still scoped to .tar.gz/.tgz per the actual use case, but nothing here artificially rejects
    other tar compressions. Returns a TarFile, usable as a context manager.'''
    if hasattr(archive_path, 'read'):
        return tarfile.open(fileobj=archive_path, mode='r:*')
    if isinstance(archive_path, bytes):
        return tarfile.open(fileobj=io.BytesIO(archive_path), mode='r:*')
    return tarfile.open(name=os.fspath(archive_path), mode='r:*')


# ---------------------------------------------------------------------------
# decompress_xml_archive() - extract everything to disk
# ---------------------------------------------------------------------------

def decompress_xml_archive(**kwargs):
    '''Extract every member of a .tar.gz/.tgz archive to a destination folder, preserving the
    archive's internal structure. Does NOT filter by file type - everything in the archive is
    extracted as-is (use xml_archive_import() instead if you only want the XML content, flattened
    to tables, without writing anything to disk).
    kwargs:
      archive_path - path/Path/raw bytes/file-like (prompts via GUI if not given)
      destination_folder - folder to extract into (prompts via GUI if not given); created if it
        doesn't already exist
    Returns the list of extracted FILE paths (directory entries within the archive are not
    included in the returned list, though they are still created on disk as needed).
    '''
    ass_var = _check_assignment(function_name='decompress_xml_archive')
    archive_path = kwargs.get('archive_path', None)
    if archive_path is None:
        archive_path = g_sel_file(title='decompress_xml_archive(): select archive',
                                  filetypes=ARCHIVE_FILETYPES)
        if not archive_path:
            print('No archive selected: decompress_xml_archive() cancelled.\n')
            return None
        if 'archive_path' not in kwargs:
            _add_kwarg_to_last_command('archive_path', _quoted(archive_path),
                                       fn_name='decompress_xml_archive')

    destination_folder = kwargs.get('destination_folder', None)
    if destination_folder is None:
        destination_folder = g_sel_folder(
            title='decompress_xml_archive(): select destination folder')
        if not destination_folder:
            print('No destination folder selected: decompress_xml_archive() cancelled.\n')
            return None
        if 'destination_folder' not in kwargs:
            _add_kwarg_to_last_command('destination_folder', _quoted(destination_folder),
                                       fn_name='decompress_xml_archive')

    extracted = _decompress_xml_archive_core(archive_path, destination_folder)
    if ass_var:
        print('Extraction complete. Assigning list of extracted file paths to variable '
              '<{}>.'.format(ass_var))
    return extracted
decompress_xml_archive.desc = 'Extract every file in a .tar.gz/.tgz archive to a folder'


def _decompress_xml_archive_core(archive_path, destination_folder):
    '''Pure extraction logic (no GUI/prompting/history side effects). Uses tarfile's 'data'
    extraction filter (added in Python 3.12, this project's pinned version) - the safe default
    that rejects path-traversal / device-file / absolute-path member tricks, closing a
    known extractall()-without-filter security hole rather than relying on its old, unsafe
    implicit default.'''
    os.makedirs(destination_folder, exist_ok=True)
    with _open_archive(archive_path) as tar:
        members = tar.getmembers()
        print('Extracting {} member(s) to <{}>...'.format(len(members), destination_folder))
        with click.progressbar(members, fill_char='*', empty_char=' ',
                               label='Extracting') as items:
            for member in items:
                tar.extract(member, path=destination_folder, filter='data')
        file_paths = [os.path.normpath(os.path.join(destination_folder, member.name))
                     for member in members if member.isfile()]
    print('Done. Extracted {} file(s).\n'.format(len(file_paths)))
    return file_paths


# ---------------------------------------------------------------------------
# xml_archive_import() - flatten every XML member into a dict of tables
# ---------------------------------------------------------------------------

def _parse_archive_import_args(**kwargs):
    '''Resolve xml_archive_import()'s kwargs: archive_path (prompted via GUI - no folder-vs-file
    ambiguity like xml_import()'s source, since this always opens one archive file) plus the same
    curated flattening-kwarg subset xml_import() prompts for, via the shared
    _resolve_flatten_kwargs(). kwargs may include the internal-use-only '_caller_fn_name', set by
    data_import() so prompted-for values are baked into the caller's history line, not
    xml_archive_import's (mirrors _parse_xml_args's/_parse_csv_args's contract).'''
    fn_name = kwargs.pop('_caller_fn_name', 'xml_archive_import')

    archive_path = kwargs.get('archive_path', None)
    if archive_path is None:
        archive_path = g_sel_file(title='xml_archive_import(): select archive',
                                  filetypes=ARCHIVE_FILETYPES)
        if not archive_path:
            print('No archive selected: xml_archive_import() cancelled.\n')
            return None
        if 'archive_path' not in kwargs:
            _add_kwarg_to_last_command('archive_path', _quoted(archive_path), fn_name=fn_name)

    resolved = _resolve_flatten_kwargs(kwargs, fn_name)
    resolved['archive_path'] = archive_path
    return resolved


def xml_archive_import(**kwargs):
    '''Parse and flatten every .xml member inside a .tar.gz/.tgz archive into a list-of-lists
    table, applying one shared set of parameters across every member. Non-.xml members are
    skipped with a warning. No archive export is provided.
    kwargs:
      archive_path - path/Path/raw bytes/file-like (prompts via GUI if not given)
      record_path, max_depth, residual_format, list_strategy, list_strategy_overrides,
        aggregate_format, aggregate_delimiter, max_indexed_items, force_list, path_separator,
        attribute_prefix, text_key, include_attributes, include_text, namespace_mode,
        empty_value, header_row, column_order, max_columns, max_rows, on_malformed,
        return_metadata, low_memory - identical meaning to xml_import()'s kwargs of the same name
        (see its docstring for each) - the SAME set of values is applied to every XML member in
        the archive; column_order='stable' unifies columns across every XML member in the
        archive, exactly like xml_import()'s folder-of-files bulk mode unifies across files.
      _caller_fn_name - [INTERNAL USE] set by data_import() so prompted-for values are baked
        into the caller's history line, not this function's.

    Each archive member's raw bytes are read fully into memory (one member at a time - not the
    whole archive at once) before flattening, since a tar/gzip member's own stream isn't
    independently seekable and low_memory=True's record_path=None auto-detection needs to
    re-read its source to sniff the repeating tag; low_memory=True still avoids building the full
    lxml DOM tree from those bytes, which is where the real memory blowup would occur for large
    XML documents - buffering one member's raw bytes first doesn't defeat that.

    Returns dict[member_name] -> list-of-lists (dict[member_name] -> (table, metadata) if
    return_metadata=True), keyed by the member's full path within the archive, so a member nested
    in a subfolder keeps that folder in its key (e.g. 'orders/2024/jan.xml').
    '''
    resolved = _parse_archive_import_args(**kwargs)
    if resolved is None:
        return None
    return _xml_archive_import_core(**resolved)
xml_archive_import.desc = 'Flatten every XML member of a .tar.gz/.tgz archive to list-of-lists'


def _xml_archive_import_core(archive_path, *, record_path=None, max_depth=None,
                             residual_format='xml', list_strategy='explode',
                             list_strategy_overrides=None, aggregate_format='json',
                             aggregate_delimiter=' | ', max_indexed_items=10, force_list=None,
                             path_separator='.', attribute_prefix='@', text_key='#text',
                             include_attributes=True, include_text=True, namespace_mode='strip',
                             empty_value='', header_row=True, column_order='discovery',
                             max_columns=2000, max_rows=None, on_malformed='raise',
                             return_metadata=False, low_memory=False):
    '''Pure archive-import logic (no GUI/prompting/history side effects).'''
    opts = _make_flatten_opts(max_depth=max_depth, residual_format=residual_format,
        list_strategy=list_strategy, list_strategy_overrides=list_strategy_overrides,
        aggregate_format=aggregate_format, aggregate_delimiter=aggregate_delimiter,
        max_indexed_items=max_indexed_items, force_list=force_list,
        path_separator=path_separator, attribute_prefix=attribute_prefix, text_key=text_key,
        include_attributes=include_attributes, include_text=include_text,
        namespace_mode=namespace_mode)

    with _open_archive(archive_path) as tar:
        file_members = [m for m in tar.getmembers() if m.isfile()]
        xml_members = [m for m in file_members if m.name.lower().endswith('.xml')]
        skipped = [m for m in file_members if not m.name.lower().endswith('.xml')]
        for member in skipped:
            print('xml_archive_import(): WARNING: skipping non-XML archive member: {}'.format(
                member.name))

        if not xml_members:
            print('xml_archive_import(): WARNING: no .xml members found in archive.')
            return {}

        with click.progressbar(xml_members, fill_char='*', empty_char=' ',
                               label='Reading archive members') as members_iter:
            named_sources = [(member.name, tar.extractfile(member).read())
                             for member in members_iter]

    results = _xml_import_bulk_core_from_sources(named_sources, record_path=record_path,
        opts=opts, header_row=header_row, column_order=column_order, max_columns=max_columns,
        max_rows=max_rows, on_malformed=on_malformed, empty_value=empty_value,
        return_metadata=return_metadata, low_memory=low_memory, item_noun='archive member')

    print('\nxml_archive_import(): archive import complete. {} XML member(s) processed, {} '
          'non-XML member(s) skipped.\n'.format(len(xml_members), len(skipped)))
    return results
