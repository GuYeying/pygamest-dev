$f = 'D:\Projects\Rust\starfish\crates\starfish-pygame\src\video.rs'
$t = Get-Content $f -Raw
$old = @'
    pub fn open(&self, path: impl Into<String>) -> Result<Video, VideoError> {
        Ok(Video {
            inner: pollster::block_on(self.inner.open(path))?,
            frame_cache: std::cell::RefCell::new(None),
        })
    }
}
'@
$new = @'
    pub fn open(&self, path: impl Into<String>) -> Result<Video, VideoError> {
        Ok(Video {
            inner: pollster::block_on(self.inner.open(path))?,
            frame_cache: std::cell::RefCell::new(None),
        })
    }

    /// 从 BaseVideo 包装（**wasm 异步 open 的完成侧接线口**——pollster::
    /// block_on 在 wasm 主线程不可用，open 拆两半：spawn_local 发起 +
    /// _open_take 完成侧经此包装，2026-11-21 video wasm 接线批次）
    pub(crate) fn from_base(base: starfish_video::Video) -> Self {
        Self {
            inner: base,
            frame_cache: std::cell::RefCell::new(None),
        }
    }
}
'@
if ($t.Contains($old)) {
    Set-Content $f ($t.Replace($old, $new)) -Encoding UTF8 -NoNewline
    Write-Output 'REPLACED'
} else {
    Write-Output 'NO_MATCH'
}
