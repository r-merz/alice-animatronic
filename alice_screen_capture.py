from __future__ import annotations

import tempfile
import threading
from pathlib import Path
from typing import Optional

import AppKit
import Foundation
import Quartz


class AliceScreenCapture:
    """
    Captures the Mac's built-in display regardless of which
    monitor contains the Alice interface window.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._built_in_display_id: Optional[int] = None

    def find_builtin_display_id(self) -> Optional[int]:
        """
        Return the active built-in laptop display ID.

        Returns None when no active built-in display exists,
        such as some closed-lid configurations.
        """
        for screen in AppKit.NSScreen.screens():
            description = screen.deviceDescription()

            display_value = description.get(
                "NSScreenNumber"
            )

            if display_value is None:
                continue

            display_id = int(display_value)

            try:
                is_builtin = bool(
                    Quartz.CGDisplayIsBuiltin(
                        display_id
                    )
                )
            except Exception as ex:
                print(
                    "Could not inspect display "
                    f"{display_id}: {ex}"
                )
                continue

            if is_builtin:
                return display_id

        return None

    def resolve_capture_display_id(self) -> int:
        """
        Prefer the built-in Mac display.

        Fall back to the current macOS main display when the
        built-in display is unavailable.
        """
        display_id = (
            self.find_builtin_display_id()
        )

        if display_id is not None:
            self._built_in_display_id = (
                display_id
            )

            return display_id

        fallback_id = int(
            Quartz.CGMainDisplayID()
        )

        print(
            "Built-in display is unavailable; "
            "capturing the macOS main display instead."
        )

        return fallback_id

    def describe_capture_display(self) -> dict:
        display_id = (
            self.resolve_capture_display_id()
        )

        bounds = Quartz.CGDisplayBounds(
            display_id
        )

        return {
            "display_id": display_id,
            "is_builtin": bool(
                Quartz.CGDisplayIsBuiltin(
                    display_id
                )
            ),
            "origin_x": int(
                bounds.origin.x
            ),
            "origin_y": int(
                bounds.origin.y
            ),
            "logical_width": int(
                bounds.size.width
            ),
            "logical_height": int(
                bounds.size.height
            ),
            "pixel_width": int(
                Quartz.CGDisplayPixelsWide(
                    display_id
                )
            ),
            "pixel_height": int(
                Quartz.CGDisplayPixelsHigh(
                    display_id
                )
            ),
        }

    def capture_builtin_display(
        self,
        output_path: Optional[
            str | Path
        ] = None,
    ) -> Path:
        """
        Capture only the built-in Mac display and save it as PNG.
        """
        with self._lock:
            display_id = (
                self.resolve_capture_display_id()
            )

            cg_image = (
                Quartz.CGDisplayCreateImage(
                    display_id
                )
            )

            if cg_image is None:
                raise RuntimeError(
                    "macOS did not return a screenshot. "
                    "Check Screen Recording permission."
                )

            if output_path is None:
                temporary_file = (
                    tempfile.NamedTemporaryFile(
                        prefix="alice_screen_",
                        suffix=".png",
                        delete=False,
                    )
                )

                temporary_file.close()

                destination_path = Path(
                    temporary_file.name
                )
            else:
                destination_path = Path(
                    output_path
                ).expanduser().resolve()

                destination_path.parent.mkdir(
                    parents=True,
                    exist_ok=True,
                )

            destination_url = (
                Foundation.NSURL
                .fileURLWithPath_(
                    str(destination_path)
                )
            )

            image_destination = (
                Quartz
                .CGImageDestinationCreateWithURL(
                    destination_url,
                    "public.png",
                    1,
                    None,
                )
            )

            if image_destination is None:
                raise RuntimeError(
                    "Could not create the PNG "
                    "image destination."
                )

            Quartz.CGImageDestinationAddImage(
                image_destination,
                cg_image,
                None,
            )

            saved = bool(
                Quartz
                .CGImageDestinationFinalize(
                    image_destination
                )
            )

            if not saved:
                raise RuntimeError(
                    "Could not save the built-in "
                    "display screenshot."
                )

            return destination_path
    def capture_builtin_display_bytes(
        self,
    ) -> bytes:
        image_path = (
            self.capture_builtin_display()
        )

        try:
            return image_path.read_bytes()

        finally:
            try:
                image_path.unlink()
            except OSError:
                pass