import React, { useRef, useState } from 'react';
import PropTypes from 'prop-types';

/**
 * UploadDropzone — clinical image upload area with drag-and-drop support.
 * Matches the Stitch "01 Image Intake" design section with subdued clinical styling.
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
    <div className="w-full bg-surface-container-low rounded-2xl p-6 md:p-10 border border-outline-variant/15 shadow-card-subtle flex flex-col items-center justify-center relative overflow-hidden">
      {/* Background subtle clinical grid */}
      <div className="absolute inset-0 clinical-grid opacity-30 pointer-events-none" />

      <div className="w-full max-w-2xl text-center relative z-10">
        {/* Section Header */}
        <div className="flex items-center justify-center gap-2.5 mb-6 md:mb-8">
          <div className="p-2 rounded-lg bg-primary/10 border border-primary/20 flex items-center justify-center">
            <span className="material-symbols-outlined text-primary text-xl md:text-2xl">upload_file</span>
          </div>
          <span className="text-sm md:text-base font-bold text-primary tracking-widest uppercase font-mono">
            01 Image Intake
          </span>
          <span className="px-2 py-0.5 rounded text-3xs font-mono font-bold bg-surface-container-highest text-tertiary border border-outline-variant/20 uppercase">
            Step 1 of 3
          </span>
        </div>

        {/* Drop Zone Box */}
        <div
          className={`
            w-full border-2 rounded-2xl flex flex-col items-center justify-center
            p-8 md:p-14 text-center bg-surface-container-lowest/60 backdrop-blur-sm
            transition-all duration-300 cursor-pointer group relative overflow-hidden
            ${isDragOver
              ? 'border-primary bg-primary/10 shadow-glow-md scale-[1.01]'
              : 'border-dashed border-outline-variant/40 hover:border-primary/60 hover:bg-surface-container-lowest/90'
            }
          `}
          id="drop-zone"
          role="button"
          tabIndex={0}
          aria-label="Upload clinical image"
          onDrop={handleDrop}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onClick={handleClick}
          onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && handleClick()}
        >
          {/* Corner Crosshairs / Reticle Accents for Clinical aesthetic */}
          <div className="absolute top-2 left-2 w-3 h-3 border-t-2 border-l-2 border-outline-variant/50 group-hover:border-primary transition-colors pointer-events-none" />
          <div className="absolute top-2 right-2 w-3 h-3 border-t-2 border-r-2 border-outline-variant/50 group-hover:border-primary transition-colors pointer-events-none" />
          <div className="absolute bottom-2 left-2 w-3 h-3 border-b-2 border-l-2 border-outline-variant/50 group-hover:border-primary transition-colors pointer-events-none" />
          <div className="absolute bottom-2 right-2 w-3 h-3 border-b-2 border-r-2 border-outline-variant/50 group-hover:border-primary transition-colors pointer-events-none" />

          {!isLoading ? (
            <div className="flex flex-col items-center" data-testid="idle-state">
              {/* Diagnostic Intake Icon */}
              <div className="w-16 h-16 md:w-20 md:h-20 rounded-2xl bg-surface-container-high/80 border border-outline-variant/30 flex items-center justify-center mb-5 group-hover:scale-105 group-hover:border-primary/50 group-hover:shadow-glow-sm transition-all duration-300">
                <span className="material-symbols-outlined text-3xl md:text-4xl text-primary transition-transform group-hover:scale-110">
                  radiology
                </span>
              </div>

              <h3 className="text-base md:text-lg font-bold mb-2 text-on-surface tracking-tight group-hover:text-primary transition-colors">
                Drag and drop clinical imagery
              </h3>

              <p className="text-xs md:text-sm text-on-surface-variant mb-5 max-w-sm leading-relaxed">
                DICOM, JPG, or PNG up to 50MB
              </p>

              {/* Supported Format Badges */}
              <div className="flex flex-wrap items-center justify-center gap-2">
                <span className="px-2.5 py-1 rounded-md bg-surface-container-high text-on-surface-variant text-3xs font-mono font-medium border border-outline-variant/20">
                  DICOM (.dcm)
                </span>
                <span className="px-2.5 py-1 rounded-md bg-surface-container-high text-on-surface-variant text-3xs font-mono font-medium border border-outline-variant/20">
                  JPEG / JPG
                </span>
                <span className="px-2.5 py-1 rounded-md bg-surface-container-high text-on-surface-variant text-3xs font-mono font-medium border border-outline-variant/20">
                  PNG
                </span>
                <span className="px-2.5 py-1 rounded-md bg-primary/10 text-primary text-3xs font-mono font-medium border border-primary/20">
                  Max 50 MB
                </span>
              </div>

              {/* Browse Button Prompt */}
              <div className="mt-5 text-2xs text-tertiary flex items-center gap-1.5 opacity-80 group-hover:opacity-100">
                <span className="material-symbols-outlined text-sm">touch_app</span>
                Click anywhere to browse local files
              </div>
            </div>
          ) : (
            <div className="flex flex-col items-center text-center py-4" data-testid="loading-state">
              {/* Clinical Processing Animation */}
              <div className="relative w-16 h-16 md:w-20 md:h-20 mb-6 flex items-center justify-center">
                <div className="absolute inset-0 border-2 border-primary/20 rounded-full" />
                <div className="absolute inset-0 border-2 border-primary border-t-transparent rounded-full animate-spin" />
                <div className="absolute inset-2 border-2 border-secondary/30 border-b-transparent rounded-full animate-spin" style={{ animationDirection: 'reverse', animationDuration: '1.5s' }} />
                <span className="material-symbols-outlined text-primary text-xl animate-pulse">
                  neurology
                </span>
              </div>

              <p className="text-base md:text-lg font-bold text-primary tracking-widest uppercase font-mono">
                Running AI Diagnostics...
              </p>

              <p className="text-xs md:text-sm text-on-surface-variant mt-2 font-medium">
                Processing layers and extracting features
              </p>

              {/* Inference Step Pipeline */}
              <div className="mt-6 flex items-center justify-center gap-2 max-w-md w-full">
                <div className="flex-1 h-1 rounded-full bg-primary animate-pulse" />
                <div className="flex-1 h-1 rounded-full bg-primary/40" />
                <div className="flex-1 h-1 rounded-full bg-surface-container-high" />
              </div>
              <p className="text-3xs text-outline font-mono mt-2 uppercase tracking-wider">
                Multi-layer Vision Transformer Analysis
              </p>
            </div>
          )}
        </div>

        {/* Clinical Privacy / Calibration Note */}
        <div className="mt-4 flex items-center justify-center gap-2 text-3xs text-outline">
          <span className="material-symbols-outlined text-xs">encrypted</span>
          <span>HIPAA/GDPR-compliant encrypted transmission • Local inferencing pipeline</span>
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
