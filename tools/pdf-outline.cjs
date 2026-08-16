const fs = require('fs');

const pdfLibPath = process.argv[3];
const { PDFDocument, PDFName, PDFArray } = require(pdfLibPath);

async function main() {
  const source = process.argv[2];
  const document = await PDFDocument.load(fs.readFileSync(source), {
    ignoreEncryption: true,
    updateMetadata: false,
  });
  const context = document.context;
  const pageByRef = new Map(
    document.getPages().map((page, index) => [page.ref.toString(), index + 1]),
  );

  const lookup = value => value ? context.lookup(value) : undefined;
  const outlines = lookup(document.catalog.get(PDFName.of('Outlines')));
  if (!outlines) throw new Error('PDF contains no outline dictionary');

  function destination(item) {
    let dest = item.get(PDFName.of('Dest'));
    if (!dest) {
      const action = lookup(item.get(PDFName.of('A')));
      if (action) dest = action.get(PDFName.of('D'));
    }
    const resolved = lookup(dest);
    if (!(resolved instanceof PDFArray) || resolved.size() === 0) return null;
    const pageRef = resolved.get(0);
    return pageByRef.get(pageRef.toString()) || null;
  }

  function walk(first, depth = 0) {
    let currentRef = first;
    while (currentRef) {
      const item = lookup(currentRef);
      const titleObject = lookup(item.get(PDFName.of('Title')));
      const title = titleObject && titleObject.decodeText
        ? titleObject.decodeText()
        : String(titleObject || '');
      process.stdout.write(`${'  '.repeat(depth)}${destination(item) || '?'}\t${title}\n`);
      const child = item.get(PDFName.of('First'));
      if (child) walk(child, depth + 1);
      currentRef = item.get(PDFName.of('Next'));
    }
  }

  walk(outlines.get(PDFName.of('First')));
}

main().catch(error => {
  console.error(error.stack || error);
  process.exitCode = 1;
});
