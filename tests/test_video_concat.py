from DOWN_AND_UP.video_concat import (
    build_selected_playlist_indices,
    build_video_concat_manifest,
    canonicalize_video_concat_playlist_url,
    evaluate_video_concat_compatibility,
    maybe_reverse_concat_order,
)


def _staged_item(index: int, **overrides):
    item = {
        "playlist_index": index,
        "source_url": f"https://example.test/{index}",
        "artifact_path": f"/tmp/{index}.mp4",
        "container": "mp4",
        "video_codec": "h264",
        "audio_codec": "aac",
        "width": 1280,
        "height": 720,
        "fps": 30.0,
        "has_audio": True,
    }
    item.update(overrides)
    return item


def test_build_selected_playlist_indices_forward():
    assert build_selected_playlist_indices(2, 5) == [2, 3, 4, 5]


def test_build_selected_playlist_indices_reverse():
    assert build_selected_playlist_indices(5, 2) == [5, 4, 3, 2]


def test_canonicalize_video_concat_playlist_url():
    assert (
        canonicalize_video_concat_playlist_url(
            "https://www.youtube.com/watch?v=abc123&list=PLxyz987&pp=something"
        )
        == "https://www.youtube.com/playlist?list=PLxyz987"
    )


def test_maybe_reverse_video_concat_order():
    pairs = [(2, {"id": "a"}), (3, {"id": "b"}), (4, {"id": "c"})]
    assert maybe_reverse_concat_order(pairs, False) == pairs
    assert maybe_reverse_concat_order(pairs, True) == list(reversed(pairs))


def test_build_video_concat_manifest_tracks_missing_indices():
    manifest = build_video_concat_manifest(
        playlist_url="https://youtube.com/playlist?list=abc",
        playlist_id="abc",
        playlist_title="Playlist",
        selected_indices=[2, 3, 4],
        ordered_indices=[2, 3, 4],
        staged_items=[_staged_item(2), _staged_item(4)],
        ordering="original",
        concat_policy="direct_concat_only",
    )
    assert manifest["missing_indices"] == [3]


def test_video_concat_compatibility_accepts_uniform_set():
    manifest = build_video_concat_manifest(
        playlist_url="https://youtube.com/playlist?list=abc",
        playlist_id="abc",
        playlist_title="Playlist",
        selected_indices=[1, 2],
        ordered_indices=[1, 2],
        staged_items=[_staged_item(1), _staged_item(2)],
        ordering="original",
        concat_policy="direct_concat_only",
    )
    compatibility = evaluate_video_concat_compatibility(manifest)
    assert compatibility["compatible"] is True
    assert compatibility["reason_code"] is None


def test_video_concat_compatibility_rejects_missing_artifact():
    manifest = build_video_concat_manifest(
        playlist_url="https://youtube.com/playlist?list=abc",
        playlist_id="abc",
        playlist_title="Playlist",
        selected_indices=[1, 2],
        ordered_indices=[1, 2],
        staged_items=[_staged_item(1)],
        ordering="original",
        concat_policy="direct_concat_only",
    )
    compatibility = evaluate_video_concat_compatibility(manifest)
    assert compatibility["compatible"] is False
    assert compatibility["reason_code"] == "missing_staged_artifact"
    assert compatibility["mismatch_surface"] == "artifact_presence"


def test_video_concat_compatibility_rejects_mixed_resolution():
    manifest = build_video_concat_manifest(
        playlist_url="https://youtube.com/playlist?list=abc",
        playlist_id="abc",
        playlist_title="Playlist",
        selected_indices=[1, 2],
        ordered_indices=[1, 2],
        staged_items=[_staged_item(1), _staged_item(2, width=1920, height=1080)],
        ordering="original",
        concat_policy="direct_concat_only",
    )
    compatibility = evaluate_video_concat_compatibility(manifest)
    assert compatibility["compatible"] is False
    assert compatibility["reason_code"] == "mixed_resolution"
    assert compatibility["mismatch_surface"] == "video_stream_shape"
