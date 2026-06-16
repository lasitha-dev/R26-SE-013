import React, { useRef, useState } from 'react';
import PropTypes from 'prop-types';

/**
 * UploadDropzone — clinical image upload area with drag-and-drop support.
 * Matches the Stitch "01 Image Intake" design section.
 *
 * @param {boolean}  isLoading - When true, shows the processing spinner state.
 * @param {function} onFile    - Callback invoked with the selected File object.
 */
const UploadDropzone = ({ isLoading = false, onFile }) => {
  const fileInputRef = useRef(null);
  const [isDragOver, setIsDragOver] = useState(false);

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragOver(false);
    const file = e.dataTransfer?.files?.[0];
    if (file && onFile) onFile(file);
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragOver(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    setIsDragOver(false);
  };

  const handleFileChange = (e) => {
    const file = e.target.files?.[0];
    if (file && onFile) onFile(file);
  };

  const handleClick = () => {
    if (!isLoading) fileInputRef.current?.click();
  };

  return (
    <div className="w-full bg-surface-container-low rounded-xl p-6 md:p-10 border border-outline-variant/10 shadow-2xl flex flex-col items-center justify-center">
      <div className="w-full max-w-xl text-center">
        {/* Section header */}
        <div className="flex items-center justify-center gap-3 mb-8">
          <span className="material-symbols-outlined text-primary text-3xl md:text-4xl">upload_file</span>
          <span className="text-lg md:text-xl font-bold text-primary tracking-widest uppercase">
            01 Image Intake
          </span>
        </div>

        {/* Drop zone */}
        <div
          className={`
            w-full border-2 border-dashed rounded-3xl flex flex-col items-center justify-center
            p-8 md:p-16 text-center bg-surface-container-lowest/50
            transition-all cursor-pointer group relative overflow-hidden
            ${isDragOver ? 'border-primary bg-primary/5' : 'border-outline-variant/30 hover:border-primary/50'}
          `}
          id="drop-zone"
          role="button"
          tabIndex={0}
          aria-label="Upload clinical image"
          onDrop={handleDrop}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onClick={handleClick}
          onKeyDown={(e) => e.key === 'Enter' && handleClick()}
        >
          {!isLoading ? (
            <div className="flex flex-col items-center" data-testid="idle-state">
              <div className="w-20 h-20 md:w-24 md:h-24 rounded-full bg-surface-container-highest flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
                <span className="material-symbols-outlined text-4xl md:text-5xl text-primary">add_a_photo</span>
              </div>
              <h3 className="text-lg md:text-xl font-bold mb-2 text-on-surface">
                Drag and drop clinical imagery
              </h3>
              <p className="text-sm text-on-surface-variant">DICOM, JPG, or PNG up to 50MB</p>
            </div>
          ) : (
            <div className="flex flex-col items-center text-center" data-testid="loading-state">
              <div className="w-16 h-16 md:w-20 md:h-20 border-4 border-primary border-t-transparent rounded-full animate-spin mb-6" />
              <p className="text-lg md:text-xl font-bold text-primary animate-pulse uppercase tracking-widest">
                Running AI Diagnostics...
              </p>
              <p className="text-sm text-on-surface-variant mt-2">
                Processing layers and extracting features
              </p>
            </div>
          )}
        </div>

        {/* Hidden file input */}
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*,.dcm"
          className="hidden"
          onChange={handleFileChange}
          data-testid="file-input"
          id="file-input"
        />
      </div>
    </div>
  );
};

UploadDropzone.propTypes = {
  isLoading: PropTypes.bool,
  onFile: PropTypes.func.isRequired,
};

export default UploadDropzone;
