#!/usr/bin/env python3

import argparse
import subprocess
import tempfile
import shutil
import os
import sys
import signal
import logging
from typing import List, Tuple

# e.g. booklet_pages(12,1) -> [(12,1,2,11),(10,3,4,9),(8,5,6,7)]
def booklet_pages(n: int, start_page: int = 1) -> List[Tuple[int, int, int, int]]:
    """
    Generates a list of tuples, each containing four page numbers for booklet printing.

    Parameters:
    n (int): The total number of pages.
    start_page (int): The starting page number.

    Returns:
    List[Tuple[int, int, int, int]]: A list of tuples for booklet page ordering.
    """
    logging.debug(f"Calculating booklet pages for total pages: {n}, starting at page: {start_page}")

    # Round up to the nearest multiple of 4
    n = int(n + (4 - n % 4) % 4)
    logging.debug(f"Adjusted total pages to nearest multiple of 4: {n}")

    sheets = []
    left = 1
    right = n
    offset = start_page - 1
    while left < right:
        sheet = (
            right + offset,  # Outer-right
            left + offset,   # Outer-left
            left + 1 + offset,  # Inner-left
            right - 1 + offset  # Inner-right
        )
        sheets.append(sheet)
        logging.debug(f"Added sheet: {sheet}")
        left += 2
        right -= 2

    return sheets

def booklet_pages_to_list(booklet_sheets: List[Tuple[int, int, int, int]]) -> List[int]:
    """
    Converts a list of booklet page tuples to a flat list of page numbers.

    Parameters:
    booklet_sheets (List[Tuple[int, int, int, int]]): The list of booklet page tuples.

    Returns:
    List[int]: A flat list of page numbers.
    """
    pages_list = [page for sheet in booklet_sheets for page in sheet]
    logging.debug(f"Flat page list for booklet printing: {pages_list}")
    return pages_list

def get_number_of_pages(pdf_file: str) -> int:
    """
    Gets the number of pages in a PDF file using pdftk.

    Parameters:
    pdf_file (str): The path to the PDF file.

    Returns:
    int: The number of pages in the PDF.
    """
    logging.debug(f"Getting number of pages for PDF file: {pdf_file}")
    result = subprocess.run(['pdftk', pdf_file, 'dump_data'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        logging.error(f"Failed to get number of pages: {result.stderr}")
        sys.exit(1)
    for line in result.stdout.splitlines():
        if line.startswith('NumberOfPages'):
            num_pages = int(line.strip().split(' ')[1])
            logging.debug(f"Number of pages in '{pdf_file}': {num_pages}")
            return num_pages
    logging.error("Could not find 'NumberOfPages' in pdftk output.")
    sys.exit(1)

def create_blank_pdf(output_file: str):
    """
    Creates a blank A4 PDF page using ImageMagick.

    Parameters:
    output_file (str): The path to the output blank PDF file.
    """
    logging.debug(f"Creating blank PDF page: {output_file}")
    result = subprocess.run(['convert', '-size', '595x842', 'xc:white', output_file], stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        logging.error(f"Failed to create blank PDF: {result.stderr}")
        sys.exit(1)

def add_blank_pages_to_pdf(pdf_file: str, total_pages: int):
    """
    Adds blank pages to a PDF file so that its total page count is divisible by 4.

    Parameters:
    pdf_file (str): The path to the PDF file.
    total_pages (int): The total number of pages after adding blanks.
    """
    logging.info(f"Adding blank pages to PDF '{pdf_file}' to reach total pages: {total_pages}")
    blank_pdf = os.path.join(temp_dir, 'blank.pdf')
    create_blank_pdf(blank_pdf)
    current_pages = get_number_of_pages(pdf_file)
    pages_to_add = total_pages - current_pages
    logging.debug(f"Current pages: {current_pages}, pages to add: {pages_to_add}")
    if pages_to_add <= 0:
        logging.debug("No blank pages needed.")
        return
    input_files = [pdf_file] + [blank_pdf] * pages_to_add
    output_file = os.path.join(temp_dir, 'extended_with_blanks.pdf')
    logging.debug(f"Combining files into '{output_file}': {input_files}")
    result = subprocess.run(['pdftk'] + input_files + ['cat', 'output', output_file], stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        logging.error(f"Failed to add blank pages: {result.stderr}")
        sys.exit(1)
    shutil.move(output_file, pdf_file)
    logging.debug(f"Replaced original PDF with extended PDF '{pdf_file}'")

def reorder_pdf_pages(input_pdf: str, output_pdf: str, page_order: List[int]):
    """
    Reorders pages of a PDF file using pdftk.

    Parameters:
    input_pdf (str): The input PDF file path.
    output_pdf (str): The output PDF file path.
    page_order (List[int]): The new page order.
    """
    logging.info(f"Reordering PDF pages in '{input_pdf}'")
    # Assign a handle to the input PDF
    handle = 'A'
    page_order_list = [f'{handle}{page}' for page in page_order]
    logging.debug(f"Page order: {' '.join(page_order_list)}")
    result = subprocess.run(['pdftk', f'{handle}={input_pdf}', 'cat'] + page_order_list + ['output', output_pdf], stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        logging.error(f"Failed to reorder pages: {result.stderr}")
        sys.exit(1)
    logging.debug(f"Reordered PDF saved as '{output_pdf}'")

def create_booklet_pdf(input_pdf: str, output_pdf: str):
    """
    Creates a booklet PDF from the input PDF using pdfjam.

    Parameters:
    input_pdf (str): The input PDF file path.
    output_pdf (str): The output PDF file path.
    """
    logging.info(f"Creating booklet PDF from '{input_pdf}'")
    result = subprocess.run([
        'pdfjam',
        input_pdf,
        '--landscape',
        '--a4paper',
        '--nup', '2x1',
        '--outfile', output_pdf
    ], stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        logging.error(f"Failed to create booklet PDF: {result.stderr}")
        sys.exit(1)
    logging.debug(f"Booklet PDF created at '{output_pdf}'")

def handle_cleanup(signum, frame):
    logging.info("Signal received, cleaning up temporary files.")
    if not args.keep_temp:
        shutil.rmtree(temp_dir)
        logging.debug(f"Deleted temporary directory: {temp_dir}")
    sys.exit(1)

def main():
    global args
    parser = argparse.ArgumentParser(description="Create a booklet PDF from an input PDF.")

    parser.add_argument("input_pdf", nargs='?', help="The input PDF file.")
    parser.add_argument("-o", "--output", help="The output booklet PDF file. Defaults to input filename suffixed with '-booklet.pdf'.")
    parser.add_argument("-n", "--pages", type=int, help="The total number of pages (required if --print-pages is used without input_pdf).")
    parser.add_argument("-S", "--start", type=int, default=1, help="The starting page number. Default is 1.")
    parser.add_argument("-s", "--separator", default=" ", help="The separator to use when printing the page numbers.")
    parser.add_argument("--print-pages", action='store_true', help="Print the page order for booklet printing and exit.")
    parser.add_argument("--keep-temp", action='store_true', help="Preserve the temporary directory.")
    parser.add_argument("-v", "--verbose", action='count', default=0, help="Increase verbosity level.")
    parser.add_argument("-f", "--force", action='store_true', help="Overwrite the output file if it exists.")

    args = parser.parse_args()

    # Setup logging
    log_level = max(1, logging.WARNING - (args.verbose * 10))
    logging.basicConfig(level=log_level, format='%(levelname)s: %(message)s')

    logging.debug(f"Parsed arguments: {args}")

    if args.print_pages:
        if args.input_pdf:
            total_pages = get_number_of_pages(args.input_pdf)
        elif args.pages:
            total_pages = args.pages
        else:
            logging.error("Either specify an input PDF or use -n/--pages to define the number of pages.")
            sys.exit(1)
        sheets = booklet_pages(total_pages, args.start)
        pages_list = booklet_pages_to_list(sheets)
        print(args.separator.join(map(str, pages_list)))
        sys.exit(0)

    if not args.input_pdf:
        parser.error("the following arguments are required: input_pdf")

    input_pdf = args.input_pdf
    if args.output:
        output_pdf = args.output
    else:
        input_basename = os.path.splitext(os.path.basename(input_pdf))[0]
        output_pdf = f"{input_basename}-booklet.pdf"
        logging.debug(f"No output file specified. Using default output file: {output_pdf}")

    if os.path.exists(output_pdf) and not args.force:
        logging.error(f"Output file '{output_pdf}' already exists. Use -f or --force to overwrite.")
        sys.exit(1)
    elif os.path.exists(output_pdf):
        logging.warning(f"Overwriting existing file '{output_pdf}'.")

    global temp_dir
    temp_dir = tempfile.mkdtemp(suffix='.make_booklet')
    logging.info(f"Created temporary directory: {temp_dir}")

    # Register cleanup handler
    signal.signal(signal.SIGINT, handle_cleanup)
    signal.signal(signal.SIGTERM, handle_cleanup)
    signal.signal(signal.SIGQUIT, handle_cleanup)

    try:
        extended_pdf = os.path.join(temp_dir, 'extended.pdf')
        reordered_pdf = os.path.join(temp_dir, 'reordered.pdf')

        shutil.copy(input_pdf, extended_pdf)
        logging.debug(f"Copied input PDF '{input_pdf}' to '{extended_pdf}'")

        total_pages = get_number_of_pages(extended_pdf)
        logging.info(f"Input PDF has {total_pages} pages")

        pages_needed = int(total_pages + (4 - total_pages % 4) % 4)
        logging.debug(f"Total pages needed after adding blanks: {pages_needed}")

        add_blank_pages_to_pdf(extended_pdf, pages_needed)
        total_pages = get_number_of_pages(extended_pdf)
        logging.debug(f"Total pages after adding blanks: {total_pages}")

        sheets = booklet_pages(total_pages, args.start)
        pages_list = booklet_pages_to_list(sheets)
        logging.debug(f"Reordered page list: {pages_list}")

        reorder_pdf_pages(extended_pdf, reordered_pdf, pages_list)
        create_booklet_pdf(reordered_pdf, output_pdf)

        logging.info(f"Booklet created: {output_pdf}")

    finally:
        if not args.keep_temp:
            shutil.rmtree(temp_dir)
            logging.debug(f"Deleted temporary directory: {temp_dir}")
        else:
            logging.info(f"Temporary files are preserved in: {temp_dir}")

if __name__ == "__main__":
    main()
