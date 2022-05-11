import asyncio
import os
import shutil
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from dbx.commands.sync import create_path_matcher
from dbx.sync import RemoteSyncer

from tests.unit.sync.utils import temporary_directory


def test_empty_dir():
    """
    Tests that RemoteSyncer works with an empty directory.
    """
    client = MagicMock()
    client.name = "test"
    client.base_path = "/test"
    with temporary_directory() as source, temporary_directory() as state_dir:
        matcher = create_path_matcher(source=source, includes=None, excludes=None)
        syncer = RemoteSyncer(
            client=client,
            source=source,
            dry_run=False,
            includes=None,
            excludes=None,
            full_sync=False,
            state_dir=state_dir,
            matcher=matcher,
        )

        # initially no files
        assert asyncio.run(syncer.incremental_copy()) == 0
        assert client.delete.call_count == 0
        assert client.mkdirs.call_count == 0
        assert client.put.call_count == 0

        # stil no files
        assert asyncio.run(syncer.incremental_copy()) == 0
        assert client.delete.call_count == 0
        assert client.mkdirs.call_count == 0
        assert client.put.call_count == 0


def test_single_file_put_and_delete():
    """
    Tests that RemoteSyncer can sync a file after it is created and then delete it after it is deleted.
    """
    client = AsyncMock()
    client.name = "test"
    client.base_path = "/test"
    with temporary_directory() as source, temporary_directory() as state_dir:
        matcher = create_path_matcher(source=source, includes=None, excludes=None)
        syncer = RemoteSyncer(
            client=client,
            source=source,
            dry_run=False,
            includes=None,
            excludes=None,
            full_sync=False,
            state_dir=state_dir,
            matcher=matcher,
        )

        # initially no files
        op_count = asyncio.run(syncer.incremental_copy())
        assert op_count == 0
        assert client.delete.call_count == 0
        assert client.mkdirs.call_count == 0
        assert client.put.call_count == 0

        # create a file to sync
        (Path(source) / "foo").touch()

        # sync the file
        assert asyncio.run(syncer.incremental_copy()) == 1
        assert client.delete.call_count == 0
        assert client.mkdirs.call_count == 0
        assert client.put.call_count == 1

        # should put the file remotely
        assert client.put.call_args_list[0][0] == ("foo", os.path.join(source, "foo"))

        # syncing again should result in no additional operations
        assert asyncio.run(syncer.incremental_copy()) == 0
        assert client.delete.call_count == 0
        assert client.mkdirs.call_count == 0
        assert client.put.call_count == 1

        # remove the file locally, which should cause it to be removed remotely
        os.remove(Path(source) / "foo")

        assert asyncio.run(syncer.incremental_copy()) == 1
        assert client.delete.call_count == 1
        assert client.mkdirs.call_count == 0
        assert client.put.call_count == 1

        # should delete the remote file
        assert client.delete.call_args_list[0][0] == ("foo",)

        # syncing again should result in no additional operations
        assert asyncio.run(syncer.incremental_copy()) == 0
        assert client.delete.call_count == 1
        assert client.mkdirs.call_count == 0
        assert client.put.call_count == 1


def test_put_dir_and_file_and_delete():
    """
    Tests that RemoteSyncer can sync a directory after it is created and then delete it after it is deleted.
    """

    client = AsyncMock()
    client.name = "test"
    client.base_path = "/test"
    with temporary_directory() as source, temporary_directory() as state_dir:
        matcher = create_path_matcher(source=source, includes=None, excludes=None)
        syncer = RemoteSyncer(
            client=client,
            source=source,
            dry_run=False,
            includes=None,
            excludes=None,
            full_sync=False,
            state_dir=state_dir,
            matcher=matcher,
        )

        # initially no files
        op_count = asyncio.run(syncer.incremental_copy())
        assert op_count == 0
        assert client.delete.call_count == 0
        assert client.mkdirs.call_count == 0
        assert client.put.call_count == 0

        # create a directory and a file in that directory
        (Path(source) / "foo").mkdir()
        (Path(source) / "foo" / "bar").touch()

        parent = AsyncMock()
        parent.attach_mock(client, "client")

        # directory and file should be created in the proper order
        assert asyncio.run(syncer.incremental_copy()) == 2
        assert client.delete.call_count == 0
        assert client.mkdirs.call_count == 1
        assert client.put.call_count == 1
        assert parent.mock_calls[0][0] == "client.mkdirs"
        assert parent.mock_calls[0][1] == ("foo",)
        assert parent.mock_calls[1][0] == "client.put"
        assert parent.mock_calls[1][1] == ("foo/bar", os.path.join(source, "foo", "bar"))

        # sync again.  no more ops.
        assert asyncio.run(syncer.incremental_copy()) == 0
        assert client.delete.call_count == 0
        assert client.mkdirs.call_count == 1
        assert client.put.call_count == 1

        # deleting the parent directory should result in the dir and file deleted by just the directory
        # delete call.
        parent = AsyncMock()
        parent.attach_mock(client, "client")
        shutil.rmtree(Path(source) / "foo")
        assert asyncio.run(syncer.incremental_copy()) == 1
        assert client.delete.call_count == 1
        assert client.mkdirs.call_count == 1
        assert client.put.call_count == 1
        assert parent.mock_calls[0][0] == "client.delete"
        assert parent.mock_calls[0][1] == ("foo",)

        # sync again.  no more ops.
        assert asyncio.run(syncer.incremental_copy()) == 0
        assert client.delete.call_count == 1
        assert client.mkdirs.call_count == 1
        assert client.put.call_count == 1


def test_single_file_put_twice():
    """
    Tests that RemoteSyncer can sync a file after it is created and then put it again after another update.
    """
    client = AsyncMock()
    client.name = "test"
    client.base_path = "/test"
    with temporary_directory() as source, temporary_directory() as state_dir:
        matcher = create_path_matcher(source=source, includes=None, excludes=None)
        syncer = RemoteSyncer(
            client=client,
            source=source,
            dry_run=False,
            includes=None,
            excludes=None,
            full_sync=False,
            state_dir=state_dir,
            matcher=matcher,
        )

        # initially no files
        op_count = asyncio.run(syncer.incremental_copy())
        assert op_count == 0
        assert client.delete.call_count == 0
        assert client.mkdirs.call_count == 0
        assert client.put.call_count == 0

        # create a file to sync
        (Path(source) / "foo").touch()

        # sync the file
        assert asyncio.run(syncer.incremental_copy()) == 1
        assert client.delete.call_count == 0
        assert client.mkdirs.call_count == 0
        assert client.put.call_count == 1

        # should put the file remotely
        assert client.put.call_args_list[0][0] == ("foo", os.path.join(source, "foo"))

        # syncing again should result in no additional operations
        assert asyncio.run(syncer.incremental_copy()) == 0
        assert client.delete.call_count == 0
        assert client.mkdirs.call_count == 0
        assert client.put.call_count == 1

        # modify the file
        with open(Path(source) / "foo", "w") as f:
            f.write("blah")

        assert asyncio.run(syncer.incremental_copy()) == 1
        assert client.delete.call_count == 0
        assert client.mkdirs.call_count == 0
        assert client.put.call_count == 2
