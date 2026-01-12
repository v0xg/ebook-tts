#!/usr/bin/env python3
"""CLI interface for document to audiobook converter."""

import os
import sys
from pathlib import Path

# Force CPU mode early, before torch is imported
if "--cpu" in sys.argv:
    os.environ["CUDA_VISIBLE_DEVICES"] = ""

import click
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

from .converter import PDFToAudiobook
from .progress import ProgressUpdate

console = Console()


def create_progress_callback(progress: Progress, task_id):
    """Create a progress callback for the converter."""

    def callback(update: ProgressUpdate):
        # Update progress bar
        progress.update(
            task_id,
            completed=update.percent,
            description=f"[cyan]{update.stage}[/cyan] {update.message}",
        )

        # Log chapter changes
        if update.chapter:
            progress.console.print(f"  [green]Chapter:[/green] {update.chapter}")

    return callback


@click.group()
@click.version_option(version="1.0.0")
def cli():
    """Document to Audiobook Converter using Kokoro TTS."""
    pass


@cli.command()
@click.option(
    "--input", "-i",
    "input_path",
    type=click.Path(exists=True),
    required=False,
    help="Path to the input PDF or EPUB file",
)
@click.option(
    "--pdf", "-p",
    "pdf_path",
    type=click.Path(exists=True),
    required=False,
    help="Path to the input PDF file (deprecated; use --input)",
)
@click.option(
    "--output", "-o",
    type=click.Path(),
    required=True,
    help="Path for the output audio file (.wav, .mp3, or .m4b)",
)
@click.option(
    "--voice", "-v",
    type=str,
    default="af_heart",
    help="Kokoro voice name (e.g., 'af_heart', 'bf_emma'). Use 'list-voices' command to see all.",
)
@click.option(
    "--chapters", "-c",
    type=str,
    help="Comma-separated list of chapter numbers to convert (e.g., '1,2,3')",
)
@click.option(
    "--speed", "-s",
    type=float,
    default=1.0,
    help="Speech speed multiplier (0.5-2.0, default: 1.0)",
)
@click.option(
    "--mock/--no-mock",
    default=False,
    help="Use mock TTS for testing (generates silence)",
)
@click.option(
    "--cpu/--gpu",
    default=False,
    help="Use CPU instead of GPU for inference",
)
@click.option(
    "--dict", "-d", "dict_path",
    type=click.Path(exists=True),
    default=None,
    help="Path to YAML pronunciation dictionary for custom word replacements",
)
@click.option(
    "--checkpoint", "-k",
    is_flag=True,
    default=False,
    help="Enable checkpointing for resumable conversion (recommended for long books)",
)
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="Force restart, discarding any existing checkpoint (requires --checkpoint)",
)
def convert(
    input_path: str,
    pdf_path: str,
    output: str,
    voice: str,
    chapters: str,
    speed: float,
    mock: bool,
    cpu: bool,
    dict_path: str,
    checkpoint: bool,
    force: bool,
):
    """Convert a PDF or EPUB to an audiobook."""
    console.print("[bold]Document to Audiobook Converter[/bold]")
    console.print()

    if input_path and pdf_path:
        console.print("[red]Error:[/red] Use either --input or --pdf, not both.")
        sys.exit(1)
    if not input_path and not pdf_path:
        console.print("[red]Error:[/red] Missing input file. Use --input <file>.")
        sys.exit(1)
    input_path = input_path or pdf_path

    # Parse chapters
    chapters_list = None
    if chapters:
        try:
            chapters_list = [int(c.strip()) for c in chapters.split(",")]
        except ValueError:
            console.print("[red]Error:[/red] Invalid chapter format. Use '1,2,3'")
            sys.exit(1)

    console.print(f"[dim]Using Kokoro engine with voice: {voice}[/dim]")

    # Handle checkpointing
    checkpoint_manager = None
    if force and not checkpoint:
        console.print("[yellow]Warning:[/yellow] --force requires --checkpoint, ignoring.")

    if checkpoint:
        from .checkpoint import CheckpointManager

        checkpoint_dir = CheckpointManager.get_checkpoint_dir(output)
        checkpoint_manager = CheckpointManager(checkpoint_dir)

        # Build settings dict for verification
        settings = {
            "voice": voice,
            "speed": speed,
            "dict_path": dict_path,
            "chapters": chapters,
        }

        if checkpoint_manager.exists():
            if force:
                checkpoint_manager.cleanup()
                console.print("[yellow]Discarding existing checkpoint...[/yellow]")
            else:
                valid, msg = checkpoint_manager.verify(input_path, settings)
                if valid:
                    completed, total = checkpoint_manager.get_progress()
                    pct = (completed / total * 100) if total > 0 else 0
                    console.print(
                        f"[green]Resuming from checkpoint "
                        f"({completed}/{total} chunks, {pct:.0f}% complete)[/green]"
                    )
                else:
                    console.print(f"[red]Checkpoint invalid:[/red] {msg}")
                    console.print("Use --force to discard and restart.")
                    sys.exit(1)

    # Create converter
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Starting...", total=100)

        try:
            converter = PDFToAudiobook(
                progress_callback=create_progress_callback(progress, task),
                mock_tts=mock,
                device="cpu" if cpu else "cuda",
                voice=voice,
                dictionary_path=dict_path,
                checkpoint_manager=checkpoint_manager,
            )

            result = converter.convert(
                input_path=input_path,
                output_path=output,
                chapters_to_convert=chapters_list,
                speed=speed,
            )

        except Exception as e:
            console.print(f"\n[red]Error:[/red] {e}")
            sys.exit(1)

    # Print results
    console.print()
    console.print("[bold green]Conversion complete![/bold green]")
    console.print()

    table = Table(show_header=False)
    table.add_column("Property", style="cyan")
    table.add_column("Value")

    table.add_row("Output file", result.output_path)
    table.add_row("Duration", result.duration_formatted)
    table.add_row("Chunks processed", str(result.chunks_processed))
    if result.chapters:
        table.add_row("Chapters", str(len(result.chapters)))

    console.print(table)


@cli.command()
@click.option(
    "--input", "-i",
    "input_path",
    type=click.Path(exists=True),
    required=False,
    help="Path to the PDF or EPUB file",
)
@click.option(
    "--pdf", "-p",
    "pdf_path",
    type=click.Path(exists=True),
    required=False,
    help="Path to the PDF file (deprecated; use --input)",
)
def chapters(input_path: str, pdf_path: str):
    """List chapters detected in a document."""
    if input_path and pdf_path:
        console.print("[red]Error:[/red] Use either --input or --pdf, not both.")
        sys.exit(1)
    if not input_path and not pdf_path:
        console.print("[red]Error:[/red] Missing input file. Use --input <file>.")
        sys.exit(1)
    input_path = input_path or pdf_path

    converter = PDFToAudiobook(mock_tts=True)
    detected = converter.extract_chapters(input_path)

    if not detected:
        console.print("[yellow]No chapters detected in this document.[/yellow]")
        return

    console.print(f"[bold]Found {len(detected)} chapters:[/bold]")
    console.print()

    table = Table()
    table.add_column("#", style="cyan", justify="right")
    table.add_column("Title")
    table.add_column("Page", justify="right")

    for i, ch in enumerate(detected, 1):
        table.add_row(str(i), ch.title, str(ch.start_page) if ch.start_page else "?")

    console.print(table)


@cli.command()
@click.option(
    "--input", "-i",
    "input_path",
    type=click.Path(exists=True),
    required=False,
    help="Path to the PDF or EPUB file",
)
@click.option(
    "--pdf", "-p",
    "pdf_path",
    type=click.Path(exists=True),
    required=False,
    help="Path to the PDF file (deprecated; use --input)",
)
@click.option(
    "--chars", "-n",
    type=int,
    default=2000,
    help="Number of characters to preview",
)
def preview(input_path: str, pdf_path: str, chars: int):
    """Preview processed text from a document."""
    if input_path and pdf_path:
        console.print("[red]Error:[/red] Use either --input or --pdf, not both.")
        sys.exit(1)
    if not input_path and not pdf_path:
        console.print("[red]Error:[/red] Missing input file. Use --input <file>.")
        sys.exit(1)
    input_path = input_path or pdf_path

    converter = PDFToAudiobook(mock_tts=True)
    text = converter.preview_text(input_path, max_chars=chars)

    console.print("[bold]Processed text preview:[/bold]")
    console.print()
    console.print(text)


@cli.command()
@click.option(
    "--input", "-i",
    "input_path",
    type=click.Path(exists=True),
    required=False,
    help="Path to the PDF or EPUB file",
)
@click.option(
    "--pdf", "-p",
    "pdf_path",
    type=click.Path(exists=True),
    required=False,
    help="Path to the PDF file (deprecated; use --input)",
)
@click.option(
    "--output", "-o",
    type=click.Path(),
    default=None,
    help="Output text file path (default: <pdf_name>.txt)",
)
@click.option(
    "--processed/--raw",
    default=False,
    help="Apply TTS preprocessing to text (default: raw)",
)
@click.option(
    "--include-meta/--no-meta",
    default=False,
    help="Include metadata and chapters at the top",
)
@click.option(
    "--dict", "-d", "dict_path",
    type=click.Path(exists=True),
    default=None,
    help="Path to YAML pronunciation dictionary (requires --processed)",
)
def extract(input_path: str, pdf_path: str, output: str, processed: bool, include_meta: bool, dict_path: str):
    """Extract text from a PDF or EPUB and save to a file."""
    from .chapter_detector import ChapterDetector
    from .epub_extractor import EPUBExtractor
    from .pdf_extractor import PDFExtractor
    from .pronunciation_dict import load_dictionary
    from .text_preprocessor import TextPreprocessor

    if input_path and pdf_path:
        console.print("[red]Error:[/red] Use either --input or --pdf, not both.")
        sys.exit(1)
    if not input_path and not pdf_path:
        console.print("[red]Error:[/red] Missing input file. Use --input <file>.")
        sys.exit(1)
    input_path = input_path or pdf_path

    # Determine output path
    if output is None:
        output = Path(input_path).stem + ".txt"

    console.print(f"[bold]Extracting text from:[/bold] {input_path}")

    # Extract text
    suffix = Path(input_path).suffix.lower()
    if suffix == ".epub":
        extractor = EPUBExtractor()
    else:
        extractor = PDFExtractor()
    doc = extractor.extract(input_path)

    # Detect chapters
    detector = ChapterDetector()
    chapters_list = detector.detect(doc)

    # Preprocess if requested
    if processed:
        dictionary = load_dictionary(dict_path) if dict_path else None
        preprocessor = TextPreprocessor(dictionary=dictionary)
        text = preprocessor.process(doc.text)
        console.print(f"[dim]Detected language: {preprocessor.detected_language}[/dim]")
        if dict_path:
            console.print("[dim]Applied pronunciation dictionary[/dim]")
    else:
        if dict_path:
            console.print("[yellow]Warning:[/yellow] --dict requires --processed flag")
        text = doc.text

    # Build output content
    lines = []

    if include_meta:
        lines.append("=" * 60)
        lines.append("METADATA")
        lines.append("=" * 60)
        for key, value in doc.metadata.items():
            if value:
                lines.append(f"{key}: {value}")
        lines.append("")

        if chapters_list:
            lines.append("=" * 60)
            lines.append("CHAPTERS")
            lines.append("=" * 60)
            for i, ch in enumerate(chapters_list, 1):
                if suffix == ".epub":
                    page_info = f" (section {ch.start_page})" if ch.start_page else ""
                else:
                    page_info = f" (page {ch.start_page})" if ch.start_page else ""
                lines.append(f"{i}. {ch.title}{page_info}")
            lines.append("")

        lines.append("=" * 60)
        lines.append("TEXT")
        lines.append("=" * 60)
        lines.append("")

    lines.append(text)

    # Write to file
    output_path = Path(output)
    output_path.write_text("\n".join(lines), encoding="utf-8")

    # Print summary
    console.print()
    table = Table(show_header=False)
    table.add_column("Property", style="cyan")
    table.add_column("Value")

    table.add_row("Output file", str(output_path))
    table.add_row("Characters", f"{len(text):,}")
    unit_label = "Sections" if suffix == ".epub" else "Pages"
    table.add_row(unit_label, str(doc.metadata.get("page_count", "?")))
    table.add_row("Chapters", str(len(chapters_list)) if chapters_list else "None detected")
    table.add_row("Preprocessed", "Yes" if processed else "No")

    console.print(table)
    console.print()
    console.print("[green]Text extracted successfully![/green]")


@cli.command()
def demo():
    """Run a demo conversion with mock TTS."""
    from .text_chunker import TextChunker
    from .text_preprocessor import TextPreprocessor

    console.print("[bold]Running demo...[/bold]")
    console.print()
    console.print("This demo uses mock TTS (generates silence).")
    console.print(
        "To convert a real PDF, use: [cyan]ebook-tts convert --input book.pdf --output book.wav[/cyan]"
    )
    console.print()

    sample_text = """
    Chapter 1: The Beginning

    Dr. Smith walked into the room. "Good morning," he said. "Today we'll discuss
    the fascinating world of text-to-speech synthesis."

    The audience listened intently as Prof. Johnson explained the technical details.
    "Converting text to natural speech requires careful preprocessing," she noted.

    Chapter 2: Advanced Topics

    In this chapter, we explore advanced techniques including voice cloning,
    prosody control, and multi-speaker synthesis. The possibilities are endless.
    """

    preprocessor = TextPreprocessor()
    chunker = TextChunker(max_chars=200)

    console.print("[bold]Original text:[/bold]")
    console.print(sample_text[:200] + "...")
    console.print()

    processed = preprocessor.process(sample_text)
    console.print("[bold]Processed text:[/bold]")
    console.print(processed[:200] + "...")
    console.print()

    chunks = chunker.chunk(processed)
    console.print(f"[bold]Created {len(chunks)} chunks[/bold]")
    for i, chunk in enumerate(chunks[:3], 1):
        console.print(f"  Chunk {i}: {chunk.text[:50]}...")

    console.print()
    console.print("[green]Demo complete![/green]")


@cli.command("list-voices")
@click.option(
    "--lang", "-l",
    type=click.Choice(["a", "b", "e", "f", "j", "z"]),
    default=None,
    help="Filter by language: a=American, b=British, e=Spanish, f=French, j=Japanese, z=Chinese",
)
def list_voices(lang: str):
    """List available Kokoro voices."""
    from .audio_synthesizer import KOKORO_VOICES, KokoroSynthesizer

    console.print("[bold]Available Kokoro Voices[/bold]")
    console.print()

    # Group voices by language
    lang_names = {
        "a": "American English",
        "b": "British English",
        "e": "Spanish",
        "f": "French",
        "j": "Japanese",
        "z": "Chinese",
    }

    voices = KokoroSynthesizer.list_voices_by_language(lang)

    if lang:
        console.print(f"[cyan]{lang_names.get(lang, lang)}[/cyan]")
        table = Table()
        table.add_column("Voice", style="green")
        table.add_column("Description")

        for voice_name, desc in sorted(voices.items()):
            table.add_row(voice_name, desc)

        console.print(table)
    else:
        # Group by language
        by_lang = {}
        for voice_name, (lang_code, desc) in KOKORO_VOICES.items():
            if lang_code not in by_lang:
                by_lang[lang_code] = []
            by_lang[lang_code].append((voice_name, desc))

        for lang_code in sorted(by_lang.keys()):
            console.print(f"[cyan]{lang_names.get(lang_code, lang_code)}[/cyan]")
            table = Table(show_header=False)
            table.add_column("Voice", style="green", width=15)
            table.add_column("Description")

            for voice_name, desc in sorted(by_lang[lang_code]):
                table.add_row(voice_name, desc)

            console.print(table)
            console.print()

    console.print(
        "[dim]Usage: ebook-tts convert --input book.pdf --output book.wav --voice af_heart[/dim]"
    )


@cli.command("text-to-wav")
@click.option(
    "--input", "-i",
    type=click.Path(exists=True),
    required=True,
    help="Path to input text file",
)
@click.option(
    "--output", "-o",
    type=click.Path(),
    required=True,
    help="Path for output WAV file",
)
@click.option(
    "--voice",
    type=str,
    default="af_heart",
    help="Voice name (e.g., 'af_heart', 'bf_emma')",
)
@click.option(
    "--speed", "-s",
    type=float,
    default=1.0,
    help="Speech speed multiplier (0.5-2.0, default: 1.0)",
)
@click.option(
    "--preprocess/--raw",
    default=False,
    help="Apply TTS preprocessing to text (default: raw)",
)
@click.option(
    "--dict", "-d", "dict_path",
    type=click.Path(exists=True),
    default=None,
    help="Path to YAML pronunciation dictionary for custom word replacements",
)
def text_to_wav(input: str, output: str, voice: str, speed: float, preprocess: bool, dict_path: str):
    """Convert a text file to WAV audio."""
    import numpy as np
    import soundfile as sf

    from .audio_synthesizer import KokoroSynthesizer
    from .pronunciation_dict import load_dictionary
    from .text_chunker import TextChunker
    from .text_preprocessor import TextPreprocessor

    console.print("[bold]Text to WAV Converter[/bold]")
    console.print()

    # Read text file
    text = Path(input).read_text(encoding="utf-8")

    # Skip metadata headers if present (from extract command)
    if "====" in text and "TEXT" in text:
        text = text.split("TEXT")[-1].strip("=\n ")

    console.print(f"[dim]Input: {input} ({len(text):,} characters)[/dim]")
    console.print(f"[dim]Voice: {voice}[/dim]")

    # Preprocess if requested
    if preprocess:
        dictionary = load_dictionary(dict_path) if dict_path else None
        preprocessor = TextPreprocessor(dictionary=dictionary)
        text = preprocessor.process(text)
        console.print(f"[dim]Preprocessed (language: {preprocessor.detected_language})[/dim]")
    elif dict_path:
        # If dict provided but no preprocessing, still apply dictionary
        dictionary = load_dictionary(dict_path)
        preprocessor = TextPreprocessor(dictionary=dictionary)
        text = preprocessor.process(text)
        console.print("[dim]Applied pronunciation dictionary[/dim]")

    # Initialize synthesizer
    synth = KokoroSynthesizer(voice=voice)

    # Chunk the text
    chunker = TextChunker(max_chars=400)
    chunks = chunker.chunk(text)

    console.print()

    # Synthesize with progress
    all_audio = []
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Synthesizing...", total=len(chunks))

        for i, chunk in enumerate(chunks):
            for audio in synth.synthesize(chunk.text, speed=speed):
                all_audio.append(audio)
            progress.update(task, advance=1, description=f"[cyan]Chunk {i+1}/{len(chunks)}")

    # Concatenate and save
    final_audio = np.concatenate(all_audio)
    sf.write(output, final_audio, synth.sample_rate)

    # Print results
    duration_seconds = len(final_audio) / synth.sample_rate
    hours = int(duration_seconds // 3600)
    minutes = int((duration_seconds % 3600) // 60)
    seconds = int(duration_seconds % 60)
    duration_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    console.print()
    console.print("[bold green]Conversion complete![/bold green]")
    console.print()

    table = Table(show_header=False)
    table.add_column("Property", style="cyan")
    table.add_column("Value")

    table.add_row("Output file", output)
    table.add_row("Duration", duration_str)
    table.add_row("Chunks", str(len(chunks)))
    table.add_row("Voice", voice)

    console.print(table)


if __name__ == "__main__":
    cli()
