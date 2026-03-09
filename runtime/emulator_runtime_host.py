# -*- coding: utf-8 -*-
"""
================================================================================
EMULATOR RUNTIME HOST - Libretro-Based Emulation Backend
================================================================================
Provides emulator hosting via Libretro cores using ctypes.
Enables framebuffer capture, VRAM/RAM access, and input injection.

Required for runtime text capture mode.
================================================================================
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple
from pathlib import Path
from enum import IntEnum
import ctypes
import struct
import os


class RetroDevice(IntEnum):
    """Libretro input devices."""
    NONE = 0
    JOYPAD = 1
    MOUSE = 2
    KEYBOARD = 3
    LIGHTGUN = 4
    ANALOG = 5
    POINTER = 6


class RetroJoypad(IntEnum):
    """Libretro joypad buttons."""
    B = 0
    Y = 1
    SELECT = 2
    START = 3
    UP = 4
    DOWN = 5
    LEFT = 6
    RIGHT = 7
    A = 8
    X = 9
    L = 10
    R = 11
    L2 = 12
    R2 = 13
    L3 = 14
    R3 = 15


class RetroMemory(IntEnum):
    """Libretro memory types."""
    SAVE_RAM = 0
    RTC = 1
    SYSTEM_RAM = 2
    VIDEO_RAM = 3


class RetroPixelFormat(IntEnum):
    """Libretro pixel formats."""
    XRGB1555 = 0
    XRGB8888 = 1
    RGB565 = 2


@dataclass
class SystemInfo:
    """Libretro system info."""
    library_name: str = ""
    library_version: str = ""
    need_fullpath: bool = False
    block_extract: bool = False
    valid_extensions: str = ""


@dataclass
class GameInfo:
    """Libretro game info."""
    path: str = ""
    data: bytes = field(default_factory=bytes)
    size: int = 0
    meta: str = ""


@dataclass
class FrameBuffer:
    """Captured frame buffer."""
    width: int = 0
    height: int = 0
    pitch: int = 0
    pixel_format: RetroPixelFormat = RetroPixelFormat.RGB565
    data: bytes = field(default_factory=bytes)


class EmulatorRuntimeHost:
    """
    Libretro-based emulator host using ctypes.

    Provides:
    - Frame-by-frame emulation control
    - VRAM and RAM access
    - Input injection
    - Framebuffer capture
    """

    def __init__(self, core_path: str, rom_path: str):
        """
        Initialize emulator host.

        Args:
            core_path: Path to Libretro core (.dll/.so/.dylib)
            rom_path: Path to ROM file
        """
        self.core_path = Path(core_path)
        self.rom_path = Path(rom_path)

        self._core: Optional[ctypes.CDLL] = None
        self._system_info: Optional[SystemInfo] = None
        self._game_loaded = False

        # State
        self._frame_count = 0
        self._current_frame: Optional[FrameBuffer] = None
        self._input_state: Dict[int, int] = {}
        self._pixel_format = RetroPixelFormat.RGB565

        # Callbacks
        self._video_refresh_cb: Optional[Callable] = None
        self._audio_sample_cb: Optional[Callable] = None
        self._audio_sample_batch_cb: Optional[Callable] = None
        self._input_poll_cb: Optional[Callable] = None
        self._input_state_cb: Optional[Callable] = None
        self._environment_cb: Optional[Callable] = None

        # Memory maps
        self._ram_data: bytes = b''
        self._vram_data: bytes = b''

        self._initialized = False

    def initialize(self) -> bool:
        """
        Initialize the Libretro core.

        Returns:
            True if successful
        """
        if self._initialized:
            return True

        try:
            # Load core library
            if os.name == 'nt':
                self._core = ctypes.CDLL(str(self.core_path), winmode=0)
            else:
                self._core = ctypes.CDLL(str(self.core_path))

            # Setup callbacks
            self._setup_callbacks()

            # Initialize core
            self._call_retro_init()

            # Get system info
            self._system_info = self._get_system_info()

            self._initialized = True
            return True

        except Exception as e:
            print(f"Failed to initialize core: {e}")
            return False

    def _setup_callbacks(self) -> None:
        """Setup Libretro callbacks."""
        # Video refresh callback
        RETRO_VIDEO_REFRESH = ctypes.CFUNCTYPE(
            None,
            ctypes.c_void_p,  # data
            ctypes.c_uint,    # width
            ctypes.c_uint,    # height
            ctypes.c_size_t   # pitch
        )

        def video_refresh(data, width, height, pitch):
            if data:
                size = pitch * height
                buffer = ctypes.string_at(data, size)
                self._current_frame = FrameBuffer(
                    width=width,
                    height=height,
                    pitch=pitch,
                    pixel_format=self._pixel_format,
                    data=buffer,
                )

        self._video_refresh_cb = RETRO_VIDEO_REFRESH(video_refresh)

        # Input poll callback
        RETRO_INPUT_POLL = ctypes.CFUNCTYPE(None)

        def input_poll():
            pass  # Input state is updated externally

        self._input_poll_cb = RETRO_INPUT_POLL(input_poll)

        # Input state callback
        RETRO_INPUT_STATE = ctypes.CFUNCTYPE(
            ctypes.c_int16,
            ctypes.c_uint,   # port
            ctypes.c_uint,   # device
            ctypes.c_uint,   # index
            ctypes.c_uint    # id
        )

        def input_state(port, device, index, id):
            if port == 0 and device == RetroDevice.JOYPAD:
                return self._input_state.get(id, 0)
            return 0

        self._input_state_cb = RETRO_INPUT_STATE(input_state)

        # Environment callback
        RETRO_ENVIRONMENT = ctypes.CFUNCTYPE(
            ctypes.c_bool,
            ctypes.c_uint,     # cmd
            ctypes.c_void_p    # data
        )

        def environment(cmd, data):
            # Handle common environment calls
            RETRO_ENVIRONMENT_SET_PIXEL_FORMAT = 10

            if cmd == RETRO_ENVIRONMENT_SET_PIXEL_FORMAT:
                if data:
                    fmt = ctypes.cast(data, ctypes.POINTER(ctypes.c_int)).contents.value
                    self._pixel_format = RetroPixelFormat(fmt)
                return True

            return False

        self._environment_cb = RETRO_ENVIRONMENT(environment)

        # Audio callbacks (stub)
        RETRO_AUDIO_SAMPLE = ctypes.CFUNCTYPE(
            None,
            ctypes.c_int16,   # left
            ctypes.c_int16    # right
        )

        def audio_sample(left, right):
            pass

        self._audio_sample_cb = RETRO_AUDIO_SAMPLE(audio_sample)

        RETRO_AUDIO_SAMPLE_BATCH = ctypes.CFUNCTYPE(
            ctypes.c_size_t,
            ctypes.c_void_p,  # data
            ctypes.c_size_t   # frames
        )

        def audio_sample_batch(data, frames):
            return frames

        self._audio_sample_batch_cb = RETRO_AUDIO_SAMPLE_BATCH(audio_sample_batch)

    def _call_retro_init(self) -> None:
        """Call retro_init."""
        if self._core:
            self._core.retro_init()

    def _get_system_info(self) -> SystemInfo:
        """Get system info from core."""
        if not self._core:
            return SystemInfo()

        class retro_system_info(ctypes.Structure):
            _fields_ = [
                ("library_name", ctypes.c_char_p),
                ("library_version", ctypes.c_char_p),
                ("valid_extensions", ctypes.c_char_p),
                ("need_fullpath", ctypes.c_bool),
                ("block_extract", ctypes.c_bool),
            ]

        info = retro_system_info()
        self._core.retro_get_system_info(ctypes.byref(info))

        return SystemInfo(
            library_name=info.library_name.decode() if info.library_name else "",
            library_version=info.library_version.decode() if info.library_version else "",
            valid_extensions=info.valid_extensions.decode() if info.valid_extensions else "",
            need_fullpath=info.need_fullpath,
            block_extract=info.block_extract,
        )

    def load_game(self) -> bool:
        """
        Load the ROM.

        Returns:
            True if successful
        """
        if not self._initialized:
            if not self.initialize():
                return False

        if not self._core:
            return False

        try:
            # Set callbacks
            self._core.retro_set_environment(self._environment_cb)
            self._core.retro_set_video_refresh(self._video_refresh_cb)
            self._core.retro_set_audio_sample(self._audio_sample_cb)
            self._core.retro_set_audio_sample_batch(self._audio_sample_batch_cb)
            self._core.retro_set_input_poll(self._input_poll_cb)
            self._core.retro_set_input_state(self._input_state_cb)

            # Load game
            class retro_game_info(ctypes.Structure):
                _fields_ = [
                    ("path", ctypes.c_char_p),
                    ("data", ctypes.c_void_p),
                    ("size", ctypes.c_size_t),
                    ("meta", ctypes.c_char_p),
                ]

            rom_data = self.rom_path.read_bytes()
            game = retro_game_info()
            game.path = str(self.rom_path).encode()
            game.data = ctypes.cast(
                ctypes.create_string_buffer(rom_data),
                ctypes.c_void_p
            )
            game.size = len(rom_data)
            game.meta = None

            result = self._core.retro_load_game(ctypes.byref(game))
            self._game_loaded = bool(result)

            return self._game_loaded

        except Exception as e:
            print(f"Failed to load game: {e}")
            return False

    def step_frame(self) -> None:
        """Advance emulation by one frame."""
        if not self._game_loaded or not self._core:
            return

        self._core.retro_run()
        self._frame_count += 1

    def get_frame(self) -> Optional[FrameBuffer]:
        """Get current frame buffer."""
        return self._current_frame

    def get_vram(self) -> bytes:
        """Read current VRAM state."""
        if not self._core or not self._game_loaded:
            return b''

        try:
            self._core.retro_get_memory_data.restype = ctypes.c_void_p
            self._core.retro_get_memory_size.restype = ctypes.c_size_t

            vram_ptr = self._core.retro_get_memory_data(RetroMemory.VIDEO_RAM)
            vram_size = self._core.retro_get_memory_size(RetroMemory.VIDEO_RAM)

            if vram_ptr and vram_size > 0:
                self._vram_data = ctypes.string_at(vram_ptr, vram_size)
                return self._vram_data

        except Exception:
            pass

        return b''

    def get_ram(self) -> bytes:
        """Read current RAM state."""
        if not self._core or not self._game_loaded:
            return b''

        try:
            self._core.retro_get_memory_data.restype = ctypes.c_void_p
            self._core.retro_get_memory_size.restype = ctypes.c_size_t

            ram_ptr = self._core.retro_get_memory_data(RetroMemory.SYSTEM_RAM)
            ram_size = self._core.retro_get_memory_size(RetroMemory.SYSTEM_RAM)

            if ram_ptr and ram_size > 0:
                self._ram_data = ctypes.string_at(ram_ptr, ram_size)
                return self._ram_data

        except Exception:
            pass

        return b''

    def send_input(self, button_mask: int) -> None:
        """
        Send controller input.

        Args:
            button_mask: Bitmask of pressed buttons (see RetroJoypad)
        """
        for button in RetroJoypad:
            self._input_state[button] = 1 if (button_mask & (1 << button)) else 0

    def press_button(self, button: RetroJoypad, frames: int = 1) -> None:
        """
        Press a button for specified frames.

        Args:
            button: Button to press
            frames: Number of frames to hold
        """
        self._input_state[button] = 1
        for _ in range(frames):
            self.step_frame()
        self._input_state[button] = 0

    def release_all(self) -> None:
        """Release all buttons."""
        self._input_state.clear()

    def get_frame_count(self) -> int:
        """Get current frame count."""
        return self._frame_count

    def reset(self) -> None:
        """Reset the emulation."""
        if self._core and self._game_loaded:
            self._core.retro_reset()
            self._frame_count = 0

    def close(self) -> None:
        """Close the emulator."""
        if self._core:
            if self._game_loaded:
                self._core.retro_unload_game()
            self._core.retro_deinit()
            self._core = None
            self._game_loaded = False
            self._initialized = False

    def __enter__(self):
        self.initialize()
        self.load_game()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    @property
    def is_running(self) -> bool:
        """Check if emulator is running."""
        return self._game_loaded

    @property
    def system_info(self) -> Optional[SystemInfo]:
        """Get system info."""
        return self._system_info
