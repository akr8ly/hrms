const allowedTypes = new Set(["image/jpeg", "image/png", "image/webp"]);
const maxPhotoBytes = 2 * 1024 * 1024;

function hasExpectedSignature(file, bytes) {
  const view = new Uint8Array(bytes);
  if (file.type === "image/jpeg") return view[0] === 0xff && view[1] === 0xd8 && view[2] === 0xff;
  if (file.type === "image/png") return [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a].every((value, index) => view[index] === value);
  return String.fromCharCode(...view.slice(0, 4)) === "RIFF" && String.fromCharCode(...view.slice(8, 12)) === "WEBP";
}

export async function validatePhotoFile(file) {
  if (!file) return "Choose an image file.";
  if (!allowedTypes.has(file.type) || file.size === 0 || file.size > maxPhotoBytes) {
    return "Photo must be a JPEG, PNG or WebP file up to 2 MB.";
  }
  const header = await file.slice(0, 12).arrayBuffer();
  return hasExpectedSignature(file, header) ? "" : "Photo content does not match its declared image type.";
}

export async function readPhotoFile(file) {
  const validationError = await validatePhotoFile(file);
  if (validationError) throw new Error(validationError);
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error("The image could not be read."));
    reader.onload = () => resolve(reader.result);
    reader.readAsDataURL(file);
  });
}
