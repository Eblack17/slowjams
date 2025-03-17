"""
Queue manager module for SlowJams application.

This module handles the queue of processing tasks, allowing for batch processing
of multiple files with progress tracking and management.
"""

import os
import logging
import uuid
import time
import threading
import json
from enum import Enum, auto
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Callable, Any, Union, Tuple
from queue import Queue, Empty
from datetime import datetime

# Import from core package
try:
    from core.downloader import DownloaderFactory, VideoMetadata
    from core.converter import AudioConverter, AudioFormat, ConversionOptions
    from core.processor import AudioProcessor, ProcessingOptions
except ImportError:
    # For standalone usage or testing
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from core.downloader import DownloaderFactory, VideoMetadata
    from core.converter import AudioConverter, AudioFormat, ConversionOptions
    from core.processor import AudioProcessor, ProcessingOptions

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """Status values for queue tasks."""
    PENDING = auto()    # Task is waiting to be processed
    RUNNING = auto()    # Task is currently being processed
    COMPLETED = auto()  # Task has been successfully completed
    FAILED = auto()     # Task failed to complete
    CANCELLED = auto()  # Task was cancelled by the user
    PAUSED = auto()     # Task is paused


class TaskType(Enum):
    """Types of tasks that can be queued."""
    DOWNLOAD = auto()   # Download a video from a URL
    CONVERT = auto()    # Convert a video to audio
    PROCESS = auto()    # Apply audio processing effects
    COMPLETE = auto()   # Combined task (download + convert + process)


@dataclass
class TaskProgress:
    """Progress information for a task."""
    
    percent: float = 0.0  # Progress percentage (0-100)
    status: TaskStatus = TaskStatus.PENDING
    current_step: str = ""  # Description of current step
    error_message: Optional[str] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    
    @property
    def elapsed_time(self) -> Optional[float]:
        """Return the elapsed time in seconds, if available."""
        if self.start_time is None:
            return None
        end = self.end_time if self.end_time is not None else time.time()
        return end - self.start_time
    
    @property
    def formatted_elapsed_time(self) -> str:
        """Return the elapsed time formatted as HH:MM:SS."""
        elapsed = self.elapsed_time
        if elapsed is None:
            return "00:00:00"
        
        hours, remainder = divmod(int(elapsed), 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


@dataclass
class QueueTask:
    """A task in the processing queue."""
    
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    task_type: TaskType = TaskType.COMPLETE
    created_at: float = field(default_factory=time.time)
    
    # Task parameters
    url: Optional[str] = None  # For download tasks
    input_file: Optional[str] = None  # For convert/process tasks
    output_file: Optional[str] = None  # For all tasks
    download_format: Optional[str] = None  # For download tasks
    conversion_options: Optional[ConversionOptions] = None  # For convert tasks
    processing_options: Optional[ProcessingOptions] = None  # For process tasks
    
    # Task state
    progress: TaskProgress = field(default_factory=TaskProgress)
    result_data: Dict[str, Any] = field(default_factory=dict)
    priority: int = 0  # Higher priority tasks are processed first
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the task to a dictionary for serialization."""
        task_dict = {
            "task_id": self.task_id,
            "task_type": self.task_type.name,
            "created_at": self.created_at,
            "url": self.url,
            "input_file": self.input_file,
            "output_file": self.output_file,
            "download_format": self.download_format,
            "priority": self.priority,
            "progress": {
                "percent": self.progress.percent,
                "status": self.progress.status.name,
                "current_step": self.progress.current_step,
                "error_message": self.progress.error_message,
                "start_time": self.progress.start_time,
                "end_time": self.progress.end_time
            },
            "result_data": self.result_data
        }
        
        # Convert complex objects to dicts
        if self.conversion_options:
            task_dict["conversion_options"] = {
                "format": self.conversion_options.format.name,
                "bitrate": self.conversion_options.bitrate,
                "sample_rate": self.conversion_options.sample_rate,
                "channels": self.conversion_options.channels,
                "normalize": self.conversion_options.normalize,
                "start_time": self.conversion_options.start_time,
                "end_time": self.conversion_options.end_time
            }
        
        if self.processing_options:
            task_dict["processing_options"] = {
                "output_format": self.processing_options.output_format.name,
                "output_bitrate": self.processing_options.output_bitrate,
                "normalize_output": self.processing_options.normalize_output,
                "preserve_metadata": self.processing_options.preserve_metadata,
                "slow_factor": self.processing_options.slow_factor,
                "preserve_pitch": self.processing_options.preserve_pitch,
                "reverb_enabled": self.processing_options.reverb_enabled,
                "reverb_room_size": self.processing_options.reverb_room_size,
                "reverb_wet_level": self.processing_options.reverb_wet_level,
                "pitch_enabled": self.processing_options.pitch_enabled,
                "pitch_semitones": self.processing_options.pitch_semitones
            }
        
        return task_dict
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'QueueTask':
        """Create a task from a dictionary."""
        # Create a basic task
        task = cls(
            task_id=data.get("task_id", str(uuid.uuid4())),
            task_type=TaskType[data["task_type"]] if "task_type" in data else TaskType.COMPLETE,
            created_at=data.get("created_at", time.time()),
            url=data.get("url"),
            input_file=data.get("input_file"),
            output_file=data.get("output_file"),
            download_format=data.get("download_format"),
            priority=data.get("priority", 0)
        )
        
        # Set progress
        if "progress" in data:
            progress_data = data["progress"]
            task.progress = TaskProgress(
                percent=progress_data.get("percent", 0.0),
                status=TaskStatus[progress_data["status"]] if "status" in progress_data else TaskStatus.PENDING,
                current_step=progress_data.get("current_step", ""),
                error_message=progress_data.get("error_message"),
                start_time=progress_data.get("start_time"),
                end_time=progress_data.get("end_time")
            )
        
        # Set result data
        if "result_data" in data:
            task.result_data = data["result_data"]
        
        # Set conversion options
        if "conversion_options" in data:
            opts = data["conversion_options"]
            task.conversion_options = ConversionOptions(
                format=AudioFormat[opts["format"]] if "format" in opts else AudioFormat.MP3,
                bitrate=opts.get("bitrate", "192k"),
                sample_rate=opts.get("sample_rate", 44100),
                channels=opts.get("channels", 2),
                normalize=opts.get("normalize", False),
                start_time=opts.get("start_time"),
                end_time=opts.get("end_time")
            )
        
        # Set processing options
        if "processing_options" in data:
            opts = data["processing_options"]
            task.processing_options = ProcessingOptions(
                output_format=AudioFormat[opts["output_format"]] if "output_format" in opts else AudioFormat.MP3,
                output_bitrate=opts.get("output_bitrate", "320k"),
                normalize_output=opts.get("normalize_output", True),
                preserve_metadata=opts.get("preserve_metadata", True),
                slow_factor=opts.get("slow_factor", 0.8),
                preserve_pitch=opts.get("preserve_pitch", True),
                reverb_enabled=opts.get("reverb_enabled", False),
                reverb_room_size=opts.get("reverb_room_size", 0.5),
                reverb_wet_level=opts.get("reverb_wet_level", 0.3),
                pitch_enabled=opts.get("pitch_enabled", False),
                pitch_semitones=opts.get("pitch_semitones", 0.0)
            )
        
        return task


class QueueManager:
    """
    Manages a queue of processing tasks with background workers.
    
    Features:
    - Add, remove, pause, and resume tasks
    - Progress tracking for all tasks
    - Background processing of tasks
    - Persistence for queue state
    """
    
    def __init__(self, num_workers: int = 2, 
                 temp_dir: Optional[str] = None,
                 ffmpeg_path: Optional[str] = None,
                 ffprobe_path: Optional[str] = None,
                 save_path: Optional[str] = None):
        """
        Initialize the queue manager.
        
        Args:
            num_workers: Number of worker threads to use.
            temp_dir: Directory for temporary files. If None, uses system temp dir.
            ffmpeg_path: Path to FFmpeg executable. If None, assumes it's in PATH.
            ffprobe_path: Path to FFprobe executable. If None, assumes it's in PATH.
            save_path: Path to save queue state. If None, doesn't save state.
        """
        self.task_queue = Queue()
        self.tasks: Dict[str, QueueTask] = {}
        self.num_workers = num_workers
        self.workers: List[threading.Thread] = []
        self.temp_dir = temp_dir
        self.save_path = save_path
        self.running = False
        self.paused = False
        self.lock = threading.Lock()
        
        # Background processing events
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()
        
        # Callback for progress updates
        self.progress_callback: Optional[Callable[[str, TaskProgress], None]] = None
        
        # Components for processing
        self.converter = AudioConverter(ffmpeg_path, ffprobe_path, temp_dir)
        self.processor = AudioProcessor(ffmpeg_path, ffprobe_path, temp_dir)
    
    def start(self):
        """Start the worker threads."""
        if self.running:
            return
        
        self.running = True
        self.stop_event.clear()
        self.pause_event.clear()
        
        # Load saved state if available
        if self.save_path and os.path.exists(self.save_path):
            self.load_state()
        
        # Start worker threads
        for i in range(self.num_workers):
            worker = threading.Thread(
                target=self._worker_thread,
                name=f"QueueWorker-{i}",
                daemon=True
            )
            worker.start()
            self.workers.append(worker)
        
        logger.info(f"Queue manager started with {self.num_workers} workers")
    
    def stop(self):
        """Stop the worker threads."""
        if not self.running:
            return
        
        self.running = False
        self.stop_event.set()
        self.pause_event.set()  # Unblock any paused workers
        
        # Wait for workers to finish
        for worker in self.workers:
            if worker.is_alive():
                worker.join(timeout=1.0)
        
        self.workers = []
        logger.info("Queue manager stopped")
        
        # Save state before stopping
        if self.save_path:
            self.save_state()
    
    def pause(self):
        """Pause processing."""
        if not self.running or self.paused:
            return
        
        self.paused = True
        self.pause_event.clear()
        logger.info("Queue processing paused")
    
    def resume(self):
        """Resume processing."""
        if not self.running or not self.paused:
            return
        
        self.paused = False
        self.pause_event.set()
        logger.info("Queue processing resumed")
    
    def add_task(self, task: QueueTask) -> str:
        """
        Add a task to the queue.
        
        Args:
            task: The task to add.
            
        Returns:
            The task ID.
        """
        with self.lock:
            self.tasks[task.task_id] = task
            self.task_queue.put((task.priority, task.task_id))
        
        logger.info(f"Added task {task.task_id} ({task.task_type.name}) to queue")
        
        # Save state after adding a task
        if self.save_path:
            self.save_state()
            
        return task.task_id
    
    def add_download_task(self, url: str, output_file: Optional[str] = None,
                        format_id: Optional[str] = None,
                        process_after_download: bool = True,
                        processing_options: Optional[ProcessingOptions] = None) -> str:
        """
        Add a download task to the queue.
        
        Args:
            url: URL to download.
            output_file: Path for the output file. If None, generates one.
            format_id: Specific format ID to download. If None, uses best quality.
            process_after_download: Whether to process the audio after downloading.
            processing_options: Options for audio processing if process_after_download is True.
            
        Returns:
            The task ID.
        """
        task_type = TaskType.COMPLETE if process_after_download else TaskType.DOWNLOAD
        
        task = QueueTask(
            task_type=task_type,
            url=url,
            output_file=output_file,
            download_format=format_id,
            processing_options=processing_options or ProcessingOptions.slow_jam_preset()
        )
        
        return self.add_task(task)
    
    def add_process_task(self, input_file: str, output_file: Optional[str] = None,
                       options: Optional[ProcessingOptions] = None) -> str:
        """
        Add a processing task to the queue.
        
        Args:
            input_file: Path to the input audio file.
            output_file: Path for the output file. If None, generates one.
            options: Processing options. If None, uses defaults.
            
        Returns:
            The task ID.
        """
        task = QueueTask(
            task_type=TaskType.PROCESS,
            input_file=input_file,
            output_file=output_file,
            processing_options=options or ProcessingOptions.slow_jam_preset()
        )
        
        return self.add_task(task)
    
    def get_task(self, task_id: str) -> Optional[QueueTask]:
        """
        Get a task by its ID.
        
        Args:
            task_id: The task ID.
            
        Returns:
            The task, or None if not found.
        """
        with self.lock:
            return self.tasks.get(task_id)
    
    def remove_task(self, task_id: str) -> bool:
        """
        Remove a task from the queue.
        
        Args:
            task_id: The task ID.
            
        Returns:
            True if the task was removed, False if not found.
        """
        with self.lock:
            if task_id not in self.tasks:
                return False
            
            # Can't remove tasks that are already running
            if self.tasks[task_id].progress.status == TaskStatus.RUNNING:
                return False
            
            del self.tasks[task_id]
        
        logger.info(f"Removed task {task_id} from queue")
        
        # Save state after removing a task
        if self.save_path:
            self.save_state()
            
        return True
    
    def clear_completed(self) -> int:
        """
        Remove all completed tasks from the queue.
        
        Returns:
            Number of tasks removed.
        """
        removed = 0
        
        with self.lock:
            task_ids = list(self.tasks.keys())
            for task_id in task_ids:
                if self.tasks[task_id].progress.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
                    del self.tasks[task_id]
                    removed += 1
        
        if removed > 0:
            logger.info(f"Removed {removed} completed tasks from queue")
            
            # Save state after clearing tasks
            if self.save_path:
                self.save_state()
                
        return removed
    
    def get_all_tasks(self) -> List[QueueTask]:
        """
        Get all tasks in the queue.
        
        Returns:
            List of all tasks.
        """
        with self.lock:
            return list(self.tasks.values())
    
    def cancel_task(self, task_id: str) -> bool:
        """
        Cancel a pending or running task.
        
        Args:
            task_id: The task ID.
            
        Returns:
            True if the task was cancelled, False if not found.
        """
        with self.lock:
            if task_id not in self.tasks:
                return False
            
            task = self.tasks[task_id]
            
            # Only cancel if not already completed or cancelled
            if task.progress.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
                return False
            
            task.progress.status = TaskStatus.CANCELLED
            task.progress.current_step = "Task cancelled by user"
            
            # Notify progress if callback is set
            if self.progress_callback:
                self.progress_callback(task_id, task.progress)
        
        logger.info(f"Cancelled task {task_id}")
        
        # Save state after cancelling a task
        if self.save_path:
            self.save_state()
            
        return True
    
    def set_task_priority(self, task_id: str, priority: int) -> bool:
        """
        Set the priority of a task.
        
        Args:
            task_id: The task ID.
            priority: The new priority value (higher = processed first).
            
        Returns:
            True if the priority was set, False if the task was not found.
        """
        with self.lock:
            if task_id not in self.tasks:
                return False
            
            # Only change priority of pending tasks
            if self.tasks[task_id].progress.status != TaskStatus.PENDING:
                return False
            
            self.tasks[task_id].priority = priority
        
        logger.info(f"Set priority of task {task_id} to {priority}")
        
        # Re-add task to queue with new priority
        self.task_queue.put((priority, task_id))
        
        # Save state after changing priority
        if self.save_path:
            self.save_state()
            
        return True
    
    def save_state(self):
        """Save the queue state to a file."""
        if not self.save_path:
            return
        
        try:
            with self.lock:
                tasks_data = [task.to_dict() for task in self.tasks.values()]
            
            with open(self.save_path, 'w') as f:
                json.dump(tasks_data, f, indent=2)
                
            logger.info(f"Saved queue state to {self.save_path}")
        except Exception as e:
            logger.error(f"Error saving queue state: {str(e)}")
    
    def load_state(self):
        """Load the queue state from a file."""
        if not self.save_path or not os.path.exists(self.save_path):
            return
        
        try:
            with open(self.save_path, 'r') as f:
                tasks_data = json.load(f)
            
            with self.lock:
                for task_data in tasks_data:
                    task = QueueTask.from_dict(task_data)
                    
                    # Only re-queue pending tasks
                    if task.progress.status == TaskStatus.PENDING:
                        self.tasks[task.task_id] = task
                        self.task_queue.put((task.priority, task.task_id))
                    # Keep completed/failed tasks for history
                    elif task.progress.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
                        self.tasks[task.task_id] = task
            
            logger.info(f"Loaded queue state from {self.save_path}")
        except Exception as e:
            logger.error(f"Error loading queue state: {str(e)}")
    
    def set_progress_callback(self, callback: Callable[[str, TaskProgress], None]):
        """
        Set a callback function to receive progress updates.
        
        Args:
            callback: Function that receives task_id and progress updates.
        """
        self.progress_callback = callback
    
    def _worker_thread(self):
        """Worker thread function that processes tasks from the queue."""
        while not self.stop_event.is_set():
            # Wait for tasks or stop event
            try:
                # Get next task with highest priority
                priority, task_id = self.task_queue.get(timeout=1.0)
                
                # Check if we should stop
                if self.stop_event.is_set():
                    self.task_queue.task_done()
                    break
                
                # Handle paused state
                if self.paused:
                    # Put the task back in the queue and wait for resume
                    self.task_queue.put((priority, task_id))
                    self.task_queue.task_done()
                    self.pause_event.wait(timeout=1.0)
                    continue
                
                # Process the task
                with self.lock:
                    if task_id not in self.tasks:
                        self.task_queue.task_done()
                        continue
                    
                    task = self.tasks[task_id]
                    
                    # Skip cancelled or completed tasks
                    if task.progress.status in [TaskStatus.CANCELLED, TaskStatus.COMPLETED, TaskStatus.FAILED]:
                        self.task_queue.task_done()
                        continue
                    
                    # Mark as running and set start time
                    task.progress.status = TaskStatus.RUNNING
                    task.progress.start_time = time.time()
                    task.progress.current_step = "Starting task"
                    task.progress.percent = 0.0
                
                # Notify progress if callback is set
                if self.progress_callback:
                    self.progress_callback(task_id, task.progress)
                
                try:
                    # Process task based on type
                    if task.task_type == TaskType.DOWNLOAD:
                        self._process_download_task(task)
                    elif task.task_type == TaskType.CONVERT:
                        self._process_convert_task(task)
                    elif task.task_type == TaskType.PROCESS:
                        self._process_audio_task(task)
                    elif task.task_type == TaskType.COMPLETE:
                        self._process_complete_task(task)
                    
                    # Mark as completed if successful
                    with self.lock:
                        if task_id in self.tasks and task.progress.status != TaskStatus.CANCELLED:
                            task.progress.status = TaskStatus.COMPLETED
                            task.progress.end_time = time.time()
                            task.progress.percent = 100.0
                            task.progress.current_step = "Task completed successfully"
                    
                    # Notify progress if callback is set
                    if self.progress_callback:
                        self.progress_callback(task_id, task.progress)
                        
                except Exception as e:
                    logger.error(f"Error processing task {task_id}: {str(e)}")
                    
                    # Mark as failed
                    with self.lock:
                        if task_id in self.tasks:
                            task.progress.status = TaskStatus.FAILED
                            task.progress.end_time = time.time()
                            task.progress.error_message = str(e)
                            task.progress.current_step = "Task failed"
                    
                    # Notify progress if callback is set
                    if self.progress_callback:
                        self.progress_callback(task_id, task.progress)
                
                # Save state after completing a task
                if self.save_path:
                    self.save_state()
                
                self.task_queue.task_done()
                
            except Empty:
                # No tasks in queue, just continue
                continue
            except Exception as e:
                logger.error(f"Error in worker thread: {str(e)}")
                continue
        
        logger.debug("Worker thread exiting")
    
    def _update_progress(self, task: QueueTask, percent: float, step: str):
        """
        Update task progress.
        
        Args:
            task: The task to update.
            percent: Progress percentage (0-100).
            step: Current step description.
        """
        with self.lock:
            task.progress.percent = percent
            task.progress.current_step = step
        
        # Notify progress if callback is set
        if self.progress_callback:
            self.progress_callback(task.task_id, task.progress)
    
    def _process_download_task(self, task: QueueTask):
        """
        Process a download task.
        
        Args:
            task: The task to process.
        """
        if not task.url:
            raise ValueError("No URL specified for download task")
        
        # Progress callback for download
        def progress_callback(percent):
            self._update_progress(task, percent, "Downloading video")
        
        # Create downloader and get metadata
        self._update_progress(task, 5.0, "Fetching video metadata")
        downloader = DownloaderFactory.create_downloader(task.url, self.temp_dir)
        metadata = downloader.get_metadata(task.url)
        
        # Store metadata in result data
        task.result_data["metadata"] = {
            "title": metadata.title,
            "author": metadata.author,
            "duration": metadata.duration,
            "platform": metadata.platform
        }
        
        # Download the video
        self._update_progress(task, 10.0, "Starting download")
        video_path = downloader.download(
            task.url, 
            task.download_format,
            progress_callback
        )
        
        # Store video path in result data
        task.result_data["video_path"] = video_path
        
        # Set output path if not specified
        if not task.output_file:
            task.output_file = video_path
    
    def _process_convert_task(self, task: QueueTask):
        """
        Process a conversion task.
        
        Args:
            task: The task to process.
        """
        if not task.input_file:
            raise ValueError("No input file specified for conversion task")
        
        # Use video path from download if this is part of a complete task
        if task.task_type == TaskType.COMPLETE and "video_path" in task.result_data:
            input_file = task.result_data["video_path"]
        else:
            input_file = task.input_file
        
        # Progress callback for conversion
        def progress_callback(percent):
            self._update_progress(task, percent, "Converting video to audio")
        
        # Extract audio from video
        self._update_progress(task, 5.0, "Starting audio extraction")
        options = task.conversion_options or ConversionOptions(
            format=AudioFormat.MP3,
            bitrate="320k",
            normalize=True
        )
        
        audio_path = self.converter.extract_audio(
            input_file,
            task.output_file,
            options,
            progress_callback
        )
        
        # Store audio path in result data
        task.result_data["audio_path"] = audio_path
        
        # Set output path if not specified
        if not task.output_file:
            task.output_file = audio_path
    
    def _process_audio_task(self, task: QueueTask):
        """
        Process an audio processing task.
        
        Args:
            task: The task to process.
        """
        if not task.input_file and "audio_path" not in task.result_data:
            raise ValueError("No input file specified for audio processing task")
        
        # Use audio path from conversion if this is part of a complete task
        if "audio_path" in task.result_data:
            input_file = task.result_data["audio_path"]
        else:
            input_file = task.input_file
        
        # Progress callback for processing
        def progress_callback(percent):
            self._update_progress(task, percent, "Applying audio effects")
        
        # Apply audio effects
        self._update_progress(task, 5.0, "Starting audio processing")
        options = task.processing_options or ProcessingOptions.slow_jam_preset()
        
        processed_path = self.processor.process_audio(
            input_file,
            task.output_file,
            options,
            progress_callback
        )
        
        # Store processed path in result data
        task.result_data["processed_path"] = processed_path
        
        # Set output path if not specified
        if not task.output_file:
            task.output_file = processed_path
    
    def _process_complete_task(self, task: QueueTask):
        """
        Process a complete task (download + convert + process).
        
        Args:
            task: The task to process.
        """
        # Download
        self._process_download_task(task)
        
        # Check if cancelled after download
        if task.progress.status == TaskStatus.CANCELLED:
            return
        
        # Convert
        self._process_convert_task(task)
        
        # Check if cancelled after conversion
        if task.progress.status == TaskStatus.CANCELLED:
            return
        
        # Process
        self._process_audio_task(task)


if __name__ == "__main__":
    # Example usage
    import sys
    
    logging.basicConfig(level=logging.INFO, 
                       format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    if len(sys.argv) < 2:
        print("Usage: python queue_manager.py <url>")
        sys.exit(1)
    
    url = sys.argv[1]
    
    # Progress callback
    def progress_update(task_id, progress):
        print(f"Task {task_id}: {progress.percent:.1f}% - {progress.current_step}")
    
    try:
        # Create queue manager
        manager = QueueManager(num_workers=1)
        manager.set_progress_callback(progress_update)
        manager.start()
        
        # Add download task
        options = ProcessingOptions.slow_jam_preset()
        task_id = manager.add_download_task(url, process_after_download=True, processing_options=options)
        
        print(f"Added task {task_id} to queue")
        print("Press Ctrl+C to stop")
        
        # Wait for tasks to complete
        while True:
            task = manager.get_task(task_id)
            if task and task.progress.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
                break
            time.sleep(1.0)
        
        # Show result
        task = manager.get_task(task_id)
        if task.progress.status == TaskStatus.COMPLETED:
            print(f"Task completed successfully!")
            print(f"Output file: {task.output_file}")
        elif task.progress.status == TaskStatus.FAILED:
            print(f"Task failed: {task.progress.error_message}")
        
        # Stop the manager
        manager.stop()
        
    except KeyboardInterrupt:
        print("\nStopping...")
        manager.stop()
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)