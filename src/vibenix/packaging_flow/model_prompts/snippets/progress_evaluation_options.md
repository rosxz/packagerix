Please return one of the following values based on your analysis:
- PROGRESS: The attempted improvement proceeded further in the build process, OR encountered a different error at exactly the same stage or later in the build which plausibly represents progress
- REGRESS: The previous build proceeded further than the attempted improvement, OR the new error is clearly worse/more fundamental than the previous one
- STAGNATION: Both builds fail with essentially the same error message and no meaningful difference
- BROKEN_LOG_OUTPUT: The log output appears garbled, corrupted, or unreadable (e.g., interleaved parallel output, binary data mixed with text, severe formatting issues)