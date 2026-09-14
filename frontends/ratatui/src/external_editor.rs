//! Explicit user-owned editor command, never a model/tool launch.
use super::*;
use std::os::unix::fs::OpenOptionsExt;

struct DraftFile(std::path::PathBuf);
impl Drop for DraftFile {
    fn drop(&mut self) {
        let _ = std::fs::remove_file(&self.0);
    }
}

pub fn edit(text: &str) -> io::Result<String> {
    let stamp = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default()
        .as_nanos();
    let path = DraftFile(
        std::env::temp_dir().join(format!("amplifier-draft-{}-{stamp}.md", std::process::id())),
    );
    let mut file = std::fs::OpenOptions::new()
        .write(true)
        .create_new(true)
        .mode(0o600)
        .open(&path.0)?;
    file.write_all(text.as_bytes())?;
    file.sync_all()?;
    drop(file);
    let command = std::env::var("VISUAL")
        .ok()
        .filter(|v| !v.trim().is_empty())
        .or_else(|| {
            std::env::var("EDITOR")
                .ok()
                .filter(|v| !v.trim().is_empty())
        })
        .unwrap_or_else(|| "vi".into());
    // VISUAL/EDITOR are deliberately user-authored shell commands. The private
    // filename is a positional parameter, never interpolated into shell source.
    let status = Command::new("sh")
        .arg("-c")
        .arg(format!("{command} \"$1\""))
        .arg("amplifier-editor")
        .arg(&path.0)
        .status()?;
    if !status.success() {
        return Err(io::Error::other("Editor failed; original draft retained"));
    }
    let metadata = std::fs::symlink_metadata(&path.0)?;
    if !metadata.is_file() || metadata.len() > 256 * 1024 {
        return Err(io::Error::other(
            "Editor result must be a regular UTF-8 file of at most 256 KiB",
        ));
    }
    let mut value = String::new();
    std::fs::File::open(&path.0)?
        .take(256 * 1024 + 1)
        .read_to_string(&mut value)?;
    if value.len() > 256 * 1024
        || value
            .chars()
            .any(|c| c.is_control() && c != '\n' && c != '\t' && c != '\r')
    {
        return Err(io::Error::other(
            "Editor result exceeds bounds or contains control characters",
        ));
    }
    Ok(value.replace("\r\n", "\n"))
}
