"""The container half of the tier-3 contract — one Modal app per GPU lane.

Each module here is a deployable Modal app (``modal deploy -m sepiq.zoo.modal_apps.<key>``,
through ``tools/modal_trace.py`` so the run is traced). The recipe every lane follows is
``README.md`` beside this file; the wire shape is :mod:`sepiq.zoo.modal_contract`. Nothing in
the rest of the package imports these modules: the laptop reaches them by app name.
"""
