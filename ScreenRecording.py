import customtkinter as ctk
import pyautogui
import threading
import time
import cv2
import numpy as np
from tkinter import messagebox

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class ScreenRecorder:
    def __init__(self):
        self.recording = False
        self.paused = False
        self.frames = []
        self.start_time = None
        self.thread = None

    def start_recording(self):
        if self.recording:
            return
        self.recording = True
        self.paused = False
        self.frames = []
        self.start_time = time.time()
        self.thread = threading.Thread(target=self.record)
        self.thread.start()

    def record(self):
        while self.recording:
            if not self.paused:
                screenshot = pyautogui.screenshot()
                frame = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
                self.frames.append(frame)
            time.sleep(0.1)

    def pause_recording(self):
        self.paused = True

    def resume_recording(self):
        self.paused = False

    def stop_recording(self):
        self.recording = False
        if self.thread:
            self.thread.join()
        if self.frames:
            height, width, _ = self.frames[0].shape
            out = cv2.VideoWriter("recording.avi", cv2.VideoWriter_fourcc(*"XVID"), 10, (width, height))
            for frame in self.frames:
                out.write(frame)
            out.release()
            messagebox.showinfo("Saved", "Recording saved as recording.avi")

class RecorderApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Advanced Screen Recorder")
        self.geometry("350x250")
        self.recorder = ScreenRecorder()

        self.label = ctk.CTkLabel(self, text="Recording Time: 0s", font=("Arial", 14))
        self.label.pack(pady=15)

        self.start_btn = ctk.CTkButton(self, text="Start Recording", command=self.start, width=200, fg_color="#27ae60")
        self.start_btn.pack(pady=5)

        self.pause_btn = ctk.CTkButton(self, text="Pause", command=self.pause, width=200, fg_color="#f39c12")
        self.pause_btn.pack(pady=5)

        self.resume_btn = ctk.CTkButton(self, text="Resume", command=self.resume, width=200, fg_color="#2980b9")
        self.resume_btn.pack(pady=5)

        self.stop_btn = ctk.CTkButton(self, text="Stop & Save", command=self.stop, width=200, fg_color="#c0392b")
        self.stop_btn.pack(pady=5)

        self.update_timer()

    def start(self):
        self.recorder.start_recording()

    def pause(self):
        self.recorder.pause_recording()

    def resume(self):
        self.recorder.resume_recording()

    def stop(self):
        self.recorder.stop_recording()

    def update_timer(self):
        if self.recorder.recording and not self.recorder.paused:
            elapsed = int(time.time() - self.recorder.start_time)
            self.label.configure(text=f"Recording Time: {elapsed}s")
        self.after(1000, self.update_timer)

if __name__ == "__main__":
    app = RecorderApp()
    app.mainloop()