import importlib
import sys
from types import ModuleType

import pytest


def make_fake_helper(tmp_path) -> ModuleType:
    """Create a fake controlnet_aux.mediapipe_face.mediapipe_face_common module.

    The fake helper exposes a generate_annotation function we can assert gets
    replaced by the adapter.
    """
    mod = ModuleType("controlnet_aux.mediapipe_face.mediapipe_face_common")

    def original_generate(img, max_faces, min_confidence):
        # sentinel different object
        return b"original"

    mod.generate_annotation = original_generate
    return mod


def test_nnbase_monkeypatch(monkeypatch, tmp_path):
    # Ensure pipeline package is importable
    sys.path.insert(0, str(tmp_path))

    # Create fake package structure in sys.modules
    fake_helper = make_fake_helper(tmp_path)
    monkeypatch.setitem(sys.modules, "controlnet_aux.mediapipe_face.mediapipe_face_common", fake_helper)

    # Import the NNBaseStylizer module (the code performs a local import inside _load_detector)
    from pipeline.stylizers import nn_base

    # The fake helper currently has original generate_annotation
    # call with dummy args
    assert getattr(fake_helper, "generate_annotation")(None, 0, 0.0) == b"original"

    # Call _load_detector on a lightweight subclass to trigger the patch
    class Dummy(nn_base.NNBaseStylizer):
        name = "dummy"

        def _import_detector(self):
            # Return a dummy detector placeholder
            return object()

        def _run_detector(self, rgb_pil):
            raise RuntimeError("not used")

    d = Dummy()
    # _load_detector should patch the fake helper.generate_annotation
    d._load_detector()

    # After load, the helper's generate_annotation should be the compatibility adapter
    from pipeline.compat import mediapipe_compat

    assert fake_helper.generate_annotation is mediapipe_compat.generate_annotation
