"""Upload training data to OpenAI and start fine-tuning job."""

import sys
import time
from openai import OpenAI

TRAINING_FILE = "all_messages.jsonl"
MODEL = "gpt-4.1-nano-2025-04-14"


def main():
    client = OpenAI()

    # Upload training file
    print(f"Uploading {TRAINING_FILE}...")
    try:
        with open(TRAINING_FILE, "rb") as f:
            message_file = client.files.create(
                file=f,
                purpose="fine-tune"
            )
        print(f"✓ File uploaded: {message_file.id}")
    except FileNotFoundError:
        print(f"Error: {TRAINING_FILE} not found!")
        print("Run prepare_training_data.py first to create the training data.")
        sys.exit(1)

    # Create fine-tuning job
    print(f"\nCreating fine-tuning job for model: {MODEL}...")
    job = client.fine_tuning.jobs.create(
        training_file=message_file.id,
        model=MODEL
    )

    print(f"✓ Fine-tuning job created: {job.id}")
    print(f"  Status: {job.status}")
    print(f"  Model: {job.model}")
    print(f"  Training file: {job.training_file}")

    print("\n" + "="*60)
    print("Fine-tuning job started!")
    print("="*60)
    print(f"\nJob ID: {job.id}")
    print("\nMonitoring job status (Ctrl+C to stop monitoring)...")
    print("You can also check status manually with:")
    print(f"  openai api fine_tuning.jobs.retrieve -i {job.id}")
    print()

    # Monitor job status
    try:
        while True:
            job = client.fine_tuning.jobs.retrieve(job.id)
            print(f"[{time.strftime('%H:%M:%S')}] Status: {job.status}", end="")

            if job.status == "succeeded":
                print("\n\n✓ Fine-tuning completed successfully!")
                print(f"✓ Fine-tuned model: {job.fine_tuned_model}")
                print(f"\nUpdate main.py with:")
                print(f'  GPT_MODEL_ID = "{job.fine_tuned_model}"')
                break
            elif job.status == "failed":
                print("\n\n✗ Fine-tuning failed!")
                if job.error:
                    print(f"Error: {job.error}")
                break
            elif job.status == "cancelled":
                print("\n\n✗ Fine-tuning was cancelled")
                break
            else:
                # Show progress if available
                if hasattr(job, 'trained_tokens') and job.trained_tokens:
                    print(f" | Trained tokens: {job.trained_tokens}", end="")
                print()
                time.sleep(30)  # Check every 30 seconds

    except KeyboardInterrupt:
        print("\n\nStopped monitoring. Job is still running.")
        print(f"Check status with: openai api fine_tuning.jobs.retrieve -i {job.id}")


if __name__ == "__main__":
    main()
