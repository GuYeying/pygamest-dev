//! 内存泄漏排查 harness（开发解释器专属——生产壳不编入）。
//!
//! 三件套：
//! 1. [`CountingAlloc`] 全局计数分配器（16B 头记 [回退距离, 尺寸]——
//!    活分配数/活字节精确统计，任意对齐安全）；
//! 2. RSS 采样（Windows GetProcessMemoryInfo）；
//! 3. [`start`] 监控线程（`PYGAMEST_MEMTRACE` 环境变量开启，3s 一拍）。
//!
//! 判读法：稳态循环内 `live_alloc/live_bytes` 斜率非零 = Rust 堆泄漏；
//! live 平而 RSS 涨 = GPU 驱动/交换链侧（另查）。最小化隔离法见
//! docs（任务1产出《如何调试寻找内存泄漏》）。

use std::alloc::{GlobalAlloc, Layout, System};
use std::sync::atomic::{AtomicU64, Ordering};

/// 活分配数（alloc - dealloc——泄漏最直接判据）
pub static LIVE_ALLOC: AtomicU64 = AtomicU64::new(0);
/// 活字节数（精确——含全部 Rust 堆对象）
pub static LIVE_BYTES: AtomicU64 = AtomicU64::new(0);
/// 累计分配字节（吞吐参考；单调）
pub static TOTAL_ALLOC_BYTES: AtomicU64 = AtomicU64::new(0);

const HEADER: usize = 16;

/// 计数分配器：用户区前 16B 头存 [回退到 raw 的距离, 用户尺寸]——
/// dealloc 时凭头精确回收 + 扣活字节。任意对齐（对齐上取整留 slack）。
pub struct CountingAlloc;

unsafe impl GlobalAlloc for CountingAlloc {
    unsafe fn alloc(&self, layout: Layout) -> *mut u8 {
        let align = layout.align().max(HEADER);
        let total = HEADER + layout.pad_to_align().size() + align;
        let raw = System.alloc(Layout::from_size_align_unchecked(total, HEADER));
        if raw.is_null() {
            return std::ptr::null_mut();
        }
        let user_addr = raw as usize + HEADER;
        let aligned_addr = (user_addr + align - 1) & !(align - 1);
        let meta = (aligned_addr - HEADER) as *mut usize;
        *meta = aligned_addr - raw as usize;
        *meta.add(1) = layout.size();
        LIVE_ALLOC.fetch_add(1, Ordering::Relaxed);
        LIVE_BYTES.fetch_add(layout.size() as u64, Ordering::Relaxed);
        TOTAL_ALLOC_BYTES.fetch_add(total as u64, Ordering::Relaxed);
        aligned_addr as *mut u8
    }

    unsafe fn dealloc(&self, ptr: *mut u8, _layout: Layout) {
        let meta = (ptr as usize - HEADER) as *mut usize;
        let back = *meta;
        let size = *meta.add(1);
        LIVE_ALLOC.fetch_sub(1, Ordering::Relaxed);
        LIVE_BYTES.fetch_sub(size as u64, Ordering::Relaxed);
        System.dealloc(
            (ptr as usize - back) as *mut u8,
            Layout::from_size_align_unchecked(back + size + HEADER, HEADER),
        );
    }
}

/// RSS 工作集（Windows GetProcessMemoryInfo；其余平台 0）
#[cfg(target_os = "windows")]
fn rss_bytes() -> u64 {
    use windows_sys::Win32::Foundation::HANDLE;
    use windows_sys::Win32::System::ProcessStatus::{
        GetProcessMemoryInfo, PROCESS_MEMORY_COUNTERS,
    };
    use windows_sys::Win32::System::Threading::GetCurrentProcess;
    unsafe {
        let mut pmc = PROCESS_MEMORY_COUNTERS {
            cb: std::mem::size_of::<PROCESS_MEMORY_COUNTERS>() as u32,
            PageFaultCount: 0,
            PeakWorkingSetSize: 0,
            WorkingSetSize: 0,
            QuotaPeakPagedPoolUsage: 0,
            QuotaPagedPoolUsage: 0,
            QuotaPeakNonPagedPoolUsage: 0,
            QuotaNonPagedPoolUsage: 0,
            PagefileUsage: 0,
            PeakPagefileUsage: 0,
        };
        let h: HANDLE = GetCurrentProcess();
        if GetProcessMemoryInfo(
            h,
            &mut pmc,
            std::mem::size_of::<PROCESS_MEMORY_COUNTERS>() as u32,
        ) != 0
        {
            pmc.WorkingSetSize as u64
        } else {
            0
        }
    }
}

#[cfg(not(target_os = "windows"))]
fn rss_bytes() -> u64 {
    0
}

fn mb(v: u64) -> String {
    format!("{:.1}MB", v as f64 / 1048576.0)
}

/// 监控线程启动（`PYGAMEST_MEMTRACE=1` 时开启；3s 一拍）。
/// 放 desktop_main 最前——分配器计数从进程启动即生效，监控只负责打印。
pub fn start() {
    if std::env::var("PYGAMEST_MEMTRACE").map(|v| v != "0").unwrap_or(false)
    {
        std::thread::Builder::new()
            .name("memtrace".into())
            .spawn(|| {
                let t0 = std::time::Instant::now();
                loop {
                    std::thread::sleep(std::time::Duration::from_secs(3));
                    println!(
                        "[memtrace] t={:.0}s live_alloc={} live_bytes={} total_alloc={} rss={}",
                        t0.elapsed().as_secs_f32(),
                        LIVE_ALLOC.load(Ordering::Relaxed),
                        mb(LIVE_BYTES.load(Ordering::Relaxed)),
                        mb(TOTAL_ALLOC_BYTES.load(Ordering::Relaxed)),
                        mb(rss_bytes()),
                    );
                }
            })
            .expect("memtrace 线程启动失败");
    }
}
