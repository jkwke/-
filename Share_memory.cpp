#include <windows.h>
#include "pch.h"
// 1. 常量定义
const DWORD original_return_address = 0x523FA9; // 游戏原始返回地址
const DWORD target_hook_address = 0x523FA3;    // 要覆盖的指令起始地址
const DWORD sun_soon = 0x43158F;
#define MAX_RECORDS 50

// 2. 结构体定义 (强制 1 字节对齐)
#pragma pack(push, 1)
struct SimpleData {
    DWORD Sun;   // 偏移 0
    DWORD old_value;   // 偏移 4
    DWORD level_change;   // 偏移 8
    DWORD zombie_number;     // 偏移 12
};

struct SharedMemoryBuffer {
    SimpleData data[MAX_RECORDS]; // 数组放在最前面 (偏移 0)，方便 Python 读取
    volatile long write_index;    // 索引挪到最后面 (偏移 800)
};
#pragma pack(pop)

// 3. 全局变量
SharedMemoryBuffer* g_buffer = NULL;

// 增加一个全局变量记录上一次的 level_change
DWORD g_last_level_value = -1;

void __stdcall OnHookTriggered(DWORD ediValue)
{
    HMODULE hModule = GetModuleHandle(L"PlantsVsZombies.exe");
    // 将HMODULE转换为字节指针
    BYTE* moduleBase = reinterpret_cast<BYTE*>(hModule);    
    DWORD one = *(DWORD*)(moduleBase + 0x2A9EC0);
    int ptr2 = *(DWORD*)(one + 0x7F8);//ptr2 = 61
    int current_level_val_number = ptr2;

    DWORD frist = *(DWORD*)(0x6A9EC0);
    DWORD Second = *(DWORD*)(frist + 0x768);
    int sun = *(DWORD*)(Second + 0x5560);



    DWORD Zombie_number = 0x6A7C14;

    // 2. 核心逻辑：检测变化
    if (current_level_val_number != g_last_level_value)
    {
        InterlockedExchange(&g_buffer->write_index, -1);
        memset(g_buffer->data, 0, sizeof(g_buffer->data));

        // 更新记录值
        g_last_level_value = current_level_val_number;
    }

    // 3. 原有的写入逻辑
    long raw_idx = InterlockedIncrement(&g_buffer->write_index);
    long current_idx = (raw_idx < 0 ? 0 : raw_idx) % MAX_RECORDS;



    SimpleData* slot = &g_buffer->data[current_idx];
    slot->Sun = sun;
    slot->old_value = ediValue + 0xC8; // 注意：你原代码里 oldValue = targetAddr;
    slot->level_change = current_level_val_number;
    slot->zombie_number = Zombie_number;
}


// 5. Naked Hook 中转函数
void __declspec(naked) ZombiesWriteHook()
{
    __asm
    {
        pushad                // 保存所有寄存器
        pushfd                // 保存标志位

        push edi              // 压入参数：ediValue
        call OnHookTriggered  // 调用 C 函数 (__stdcall 会自动平衡此 push)

        popfd                 // 恢复标志位
        popad                 // 恢复寄存器

        // 执行被覆盖的原始指令
        mov ecx, [edi + 0xC8]
        // 跳回原程序
        jmp [original_return_address]
    }
}

// 6. 安装 Hook
BOOL InstallHook()
{
    DWORD oldProtect;
    if (!VirtualProtect((void*)target_hook_address, 5, PAGE_EXECUTE_READWRITE, &oldProtect))
        return FALSE;

    // 计算相对跳转偏移：目标 - 当前 - 指令长度(5)
    DWORD relativeJump = (DWORD)&ZombiesWriteHook - target_hook_address - 5;

    *(BYTE*)target_hook_address = 0xE9;         // JMP
    *(DWORD*)(target_hook_address + 1) = relativeJump;

    VirtualProtect((void*)target_hook_address, 5, oldProtect, &oldProtect);


    DWORD sun_soon1;
    if (!VirtualProtect((void*)sun_soon, 1, PAGE_EXECUTE_READWRITE, &sun_soon1))
        return FALSE;

    *(BYTE*)sun_soon = 0xEB;

    VirtualProtect((void*)sun_soon, 1, sun_soon1, &sun_soon1);

    return TRUE;
}

// 7. DLL 入口
BOOL APIENTRY DllMain(HMODULE hModule, DWORD reason, LPVOID lpReserved)
{
    if (reason == DLL_PROCESS_ATTACH)
    {
        HANDLE hMapFile = CreateFileMappingW(
            INVALID_HANDLE_VALUE,
            NULL,
            PAGE_READWRITE,
            0,
            sizeof(SharedMemoryBuffer),
            L"PVZ_HOOK_SHARED_MEM"
        );

        if (hMapFile)
        {
            g_buffer = (SharedMemoryBuffer*)MapViewOfFile(
                hMapFile,
                FILE_MAP_ALL_ACCESS,
                0, 0,
                sizeof(SharedMemoryBuffer)
            );

            if (g_buffer)
            {
                // 初始化内存：索引设为 -1，第一次递增后为 0
                ZeroMemory(g_buffer, sizeof(SharedMemoryBuffer));
                g_buffer->write_index = -1;
                InstallHook();
            }
        }
    }
    else if (reason == DLL_PROCESS_DETACH)
    {
        if (g_buffer) UnmapViewOfFile(g_buffer);
    }
    return TRUE;
}
