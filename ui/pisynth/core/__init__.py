"""core — pure logic / domain layer (#308): no drawing, no device handles.

settings (persistence) · soundfonts (catalog/preset model) · audio (device
enumeration) · system (board/ip) · geometry (calibration math). Depends only on
stdlib + yaml/numpy — never on io/ or the UI.
"""
