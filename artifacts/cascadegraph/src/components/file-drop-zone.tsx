import { useRef, useState, type ReactNode } from "react";
import { cn } from "@/lib/utils";

/** The native picker inside remains the keyboard alternative; dropping only selects. */
export function FileDropZone({ children, disabled, onFiles, testId }: {
  children: ReactNode;
  disabled: boolean;
  onFiles: (files: File[]) => void;
  testId: string;
}) {
  const depth = useRef(0);
  const [dragging, setDragging] = useState(false);
  return (
    <div data-testid={testId} data-dragging={dragging && !disabled}
      className={cn("min-w-0 rounded-md border border-dashed p-3.5 transition-colors",
        dragging && !disabled ? "border-primary bg-primary/10" : "border-input/70 bg-muted/40")}
      onDragEnter={e => {
        e.preventDefault(); e.stopPropagation();
        if (!disabled && Array.from(e.dataTransfer.types).includes("Files")) {
          depth.current += 1; setDragging(true);
        }
      }}
      onDragOver={e => {
        e.preventDefault(); e.stopPropagation();
        e.dataTransfer.dropEffect = disabled ? "none" : "copy";
      }}
      onDragLeave={e => {
        e.preventDefault(); e.stopPropagation();
        depth.current = Math.max(0, depth.current - 1);
        if (!depth.current) setDragging(false);
      }}
      onDrop={e => {
        e.preventDefault(); e.stopPropagation();
        depth.current = 0; setDragging(false);
        if (!disabled && e.dataTransfer.files.length) onFiles(Array.from(e.dataTransfer.files));
      }}>
      <p className="mb-2 text-xs text-muted-foreground" aria-live="polite">
        {dragging && !disabled ? "Drop files to select them — analysis will not start." : "Drag files here or use the file picker below."}
      </p>
      {children}
    </div>
  );
}
