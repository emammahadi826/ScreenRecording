import customtkinter as ctk
import threading
import time
import cv2
import numpy as np
import mss
import pyaudio
import wave
from tkinter import messagebox, Toplevel, Scale

# --- Constants ---
# Appearance
ctk.set_appearance_mode("dark")


# Black and White Theme
BG = "#000000"      # Black
CARD = "#1c1c1c"    # Off-black
BTN_BG = "#333333"  # Gray
BTN_HOVER = "#444444" # Light Gray
TEXT = "#FFFFFF"      # White

# Audio settings
CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100

# --- Screen Recorder Logic ---
class ScreenRecorder:
    def __init__(self, monitor_index=1, fps=15):
        self.recording = False
        self.paused = False
        self.frames = []
        self.audio_frames = []
        self.start_time = None
        self.thread = None
        self.monitor_index = monitor_index
        self.fps = fps
        self._stop_event = threading.Event()

        # Feature flags
        self.record_audio = False
        self.record_webcam = False
        self.webcam_device = 0
        self.quality = "Medium"

        # Audio setup
        self.p = pyaudio.PyAudio()
        self.audio_stream = None

    def start_recording(self):
        if self.recording:
            return
        self.recording = True
        self.paused = False
        self.frames = []
        self.audio_frames = []
        self.start_time = time.time()
        self._stop_event.clear()

        if self.record_audio:
            self.audio_stream = self.p.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK)

        self.thread = threading.Thread(target=self.record, daemon=True)
        self.thread.start()

    def record(self):
        with mss.mss() as sct:
            monitor = sct.monitors[self.monitor_index]
            interval = 1.0 / self.fps
            
            cap_webcam = None
            if self.record_webcam:
                cap_webcam = cv2.VideoCapture(self.webcam_device, cv2.CAP_DSHOW)

            while not self._stop_event.is_set():
                if not self.paused and self.recording:
                    # Screen capture
                    img = sct.grab(monitor)
                    frame = np.array(img)
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)

                    # Webcam overlay
                    if self.record_webcam and cap_webcam and cap_webcam.isOpened():
                        ret, webcam_frame = cap_webcam.read()
                        if ret:
                            h, w, _ = frame.shape
                            webcam_h, webcam_w, _ = webcam_frame.shape
                            # Simple overlay at top-right
                            frame[10:10+webcam_h, w-10-webcam_w:w-10] = webcam_frame

                    self.frames.append(frame)

                    # Audio capture
                    if self.record_audio and self.audio_stream:
                        try:
                            data = self.audio_stream.read(CHUNK)
                            self.audio_frames.append(data)
                        except IOError:
                            pass # Can happen if buffer overflows

                time.sleep(interval)
            
            if cap_webcam:
                cap_webcam.release()

    def pause_recording(self):
        self.paused = True

    def resume_recording(self):
        self.paused = False

    def stop_recording(self, filename="recording.mp4"):
        self.recording = False
        self._stop_event.set()
        if self.thread:
            self.thread.join(timeout=3)

        if self.audio_stream:
            self.audio_stream.stop_stream()
            self.audio_stream.close()

        if self.frames:
            height, width, _ = self.frames[0].shape
            
            # Quality settings
            bitrate_map = {"Low": 1_000_000, "Medium": 2_500_000, "High": 5_000_000}
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            out = cv2.VideoWriter(filename, fourcc, float(self.fps), (width, height))
            
            for frame in self.frames:
                out.write(frame)
            out.release()

            # Save audio
            if self.record_audio and self.audio_frames:
                audio_filename = filename.replace(".mp4", ".wav")
                with wave.open(audio_filename, 'wb') as wf:
                    wf.setnchannels(CHANNELS)
                    wf.setsampwidth(self.p.get_sample_size(FORMAT))
                    wf.setframerate(RATE)
                    wf.writeframes(b''.join(self.audio_frames))
                
                messagebox.showinfo("Saved", f"Video saved as {filename}\nAudio saved as {audio_filename}")
            else:
                messagebox.showinfo("Saved", f"Recording saved as {filename}")
        else:
            messagebox.showinfo("No Data", "No frames were recorded.")

# --- Settings Window ---
class SettingsWindow(Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("⚙️ Settings")
        self.geometry("380x420")
        self.configure(bg=CARD)
        self.transient(master)

        self.recorder = master.recorder

        # --- Header ---
        ctk.CTkLabel(self, text="Settings", font=ctk.CTkFont(size=20, weight="bold")).pack(pady=15)

        # --- Device Settings ---
        devices_frame = ctk.CTkFrame(self, fg_color=BG)
        devices_frame.pack(pady=10, padx=20, fill="x")
        ctk.CTkLabel(devices_frame, text="Devices", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=15, pady=(10, 5))

        mic_available = self.has_microphone()
        webcam_available = self.has_webcam()

        self.audio_var = ctk.BooleanVar(value=mic_available)
        self.recorder.record_audio = mic_available
        audio_switch = ctk.CTkSwitch(devices_frame, text="Record Microphone", variable=self.audio_var, command=self.toggle_audio)
        audio_switch.pack(anchor="w", padx=15, pady=10)
        if not mic_available:
            audio_switch.configure(state="disabled")

        self.webcam_var = ctk.BooleanVar(value=webcam_available)
        self.recorder.record_webcam = webcam_available
        webcam_switch = ctk.CTkSwitch(devices_frame, text="Record Webcam", variable=self.webcam_var, command=self.toggle_webcam)
        webcam_switch.pack(anchor="w", padx=15, pady=(0, 15))
        if not webcam_available:
            webcam_switch.configure(state="disabled")

        # --- Recording Settings ---
        recording_frame = ctk.CTkFrame(self, fg_color=BG)
        recording_frame.pack(pady=10, padx=20, fill="x")
        ctk.CTkLabel(recording_frame, text="Recording", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=15, pady=(10, 5))

        # Quality
        ctk.CTkLabel(recording_frame, text="Video Quality").pack(anchor="w", padx=15, pady=(10,0))
        self.quality_var = ctk.StringVar(value=self.recorder.quality)
        quality_menu = ctk.CTkOptionMenu(recording_frame, values=["Low", "Medium", "High"], variable=self.quality_var, command=self.set_quality)
        quality_menu.pack(anchor="w", padx=15, pady=(0,10), fill="x")

        # FPS
        self.fps_label = ctk.CTkLabel(recording_frame, text=f"FPS: {self.recorder.fps}")
        self.fps_label.pack(anchor="w", padx=15, pady=(10,0))
        self.fps_slider = ctk.CTkSlider(recording_frame, from_=5, to=30, command=self.set_fps)
        self.fps_slider.set(self.recorder.fps)
        self.fps_slider.pack(anchor="w", padx=15, pady=(0,15), fill="x")


    def has_microphone(self):
        p = pyaudio.PyAudio()
        has_mic = False
        try:
            for i in range(p.get_device_count()):
                dev = p.get_device_info_by_index(i)
                if dev['maxInputChannels'] > 0:
                    has_mic = True
                    break
        finally:
            p.terminate()
        return has_mic

    def has_webcam(self):
        for i in range(5):
            cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
            if cap.isOpened():
                cap.release()
                return True
        return False

    def toggle_audio(self):
        self.recorder.record_audio = self.audio_var.get()

    def toggle_webcam(self):
        self.recorder.record_webcam = self.webcam_var.get()

    def set_quality(self, quality):
        self.recorder.quality = quality

    def set_fps(self, fps_value):
        fps = int(fps_value)
        self.recorder.fps = fps
        self.fps_label.configure(text=f"FPS: {fps}")

# --- Main Application ---
class RecorderApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Pro Screen Recorder")
        self.geometry("480x320")
        self.configure(fg_color=BG)

        self.recorder = ScreenRecorder(fps=15)
        self.settings_window = None

        # --- Header ---
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(padx=20, pady=(14, 10), fill="x")
        ctk.CTkLabel(header, text="● Pro Screen Recorder", font=ctk.CTkFont(size=20, weight="bold")).pack(side="left")
        
        self.settings_btn = ctk.CTkButton(header, text="⚙️", width=40, command=self.open_settings)
        self.settings_btn.pack(side="right")

        # --- Info Area ---
        info_frame = ctk.CTkFrame(self, corner_radius=10, fg_color=CARD)
        info_frame.pack(padx=20, pady=10, fill="x")

        self.status_label = ctk.CTkLabel(info_frame, text="Status: Idle", font=ctk.CTkFont(size=14, weight="bold"))
        self.status_label.pack(pady=(10, 5), padx=15, anchor="w")

        self.time_label = ctk.CTkLabel(info_frame, text="Duration: 0s", font=ctk.CTkFont(size=16))
        self.time_label.pack(pady=(0, 12), padx=15, anchor="w")

        # --- Main Controls ---
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=10, padx=20, fill="x")

        font_bold = ctk.CTkFont(weight="bold")
        btn_kwargs = {"height": 45, "corner_radius": 8, "fg_color": BTN_BG, "hover_color": BTN_HOVER, "font": font_bold}

        self.start_btn = ctk.CTkButton(btn_frame, text="▶ Start", command=self.start, **btn_kwargs)
        self.start_btn.pack(side="left", expand=True, padx=5)

        self.pause_btn = ctk.CTkButton(btn_frame, text="⏸ Pause", command=self.pause, **btn_kwargs)
        self.pause_btn.pack(side="left", expand=True, padx=5)

        self.resume_btn = ctk.CTkButton(btn_frame, text="⏯ Resume", command=self.resume, **btn_kwargs)
        self.resume_btn.pack(side="left", expand=True, padx=5)

        # --- Stop Button ---
        self.stop_btn = ctk.CTkButton(self, text="⏹ Stop & Save", height=50, corner_radius=10, fg_color=BTN_BG, command=self.stop, font=font_bold)
        self.stop_btn.pack(pady=10, padx=20, fill="x")

        self.update_button_states("idle")
        self.update_timer()

    def open_settings(self):
        if self.settings_window is None or not self.settings_window.winfo_exists():
            self.settings_window = SettingsWindow(self)
        self.settings_window.focus()

    def update_button_states(self, state):
        if state == "idle":
            self.start_btn.configure(state="normal")
            self.pause_btn.configure(state="disabled")
            self.resume_btn.configure(state="disabled")
            self.stop_btn.configure(state="disabled")
        elif state == "recording":
            self.start_btn.configure(state="disabled")
            self.pause_btn.configure(state="normal")
            self.resume_btn.configure(state="disabled")
            self.stop_btn.configure(state="normal")
        elif state == "paused":
            self.pause_btn.configure(state="disabled")
            self.resume_btn.configure(state="normal")

    def start(self):
        self.recorder.start_recording()
        self.status_label.configure(text="Status: Recording")
        self.update_button_states("recording")

    def pause(self):
        self.recorder.pause_recording()
        self.status_label.configure(text="Status: Paused")
        self.update_button_states("paused")

    def resume(self):
        self.recorder.resume_recording()
        self.status_label.configure(text="Status: Recording")
        self.update_button_states("recording")

    def stop(self):
        self.recorder.stop_recording()
        self.status_label.configure(text="Status: Idle")
        self.time_label.configure(text="Duration: 0s")
        self.update_button_states("idle")

    def update_timer(self):
        if self.recorder.recording and not self.recorder.paused:
            elapsed = int(time.time() - self.recorder.start_time)
            self.time_label.configure(text=f"Duration: {elapsed}s")
        self.after(500, self.update_timer)

if __name__ == "__main__":
    app = RecorderApp()
    app.mainloop()
