No. 1 Locally hosted web application that allows you to perform various operations on PDF files

## Access and OCR

Built-in login is disabled with `SECURITY_ENABLELOGIN=false`; access is restricted
by Traefik's `localaccess` middleware. Anyone allowed through that middleware can
use the application.

The UI locale is not forced. Extra OCR languages are provided as Tesseract
`.traineddata` files in the mounted `trainingData` directory, not through a
`LANGS` environment variable.

## References

- Home: https://stirlingtools.com
- Source: [GitHub - Stirling-Tools/Stirling-PDF: #1 PDF Application on GitHub that lets you edit PDFs on any device anywhere](https://github.com/Stirling-Tools/Stirling-PDF)
