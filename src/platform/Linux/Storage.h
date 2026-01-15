/*
 *
 *    Copyright (c) 2025 Project CHIP Authors
 *    All rights reserved.
 *
 *    Licensed under the Apache License, Version 2.0 (the "License");
 *    you may not use this file except in compliance with the License.
 *    You may obtain a copy of the License at
 *
 *        http://www.apache.org/licenses/LICENSE-2.0
 *
 *    Unless required by applicable law or agreed to in writing, software
 *    distributed under the License is distributed on an "AS IS" BASIS,
 *    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 *    See the License for the specific language governing permissions and
 *    limitations under the License.
 */

/**
 *    @file
 *         This file defines a class for managing client application
 *         user-editable settings. CHIP settings are partitioned into two
 *         distinct areas:
 *
 *         1. immutable / durable: factory parameters (CHIP_DEFAULT_FACTORY_PATH)
 *         2. mutable / ephemeral: user parameters (CHIP_DEFAULT_CONFIG_PATH/CHIP_DEFAULT_DATA_PATH)
 *
 *         The ephemeral partition should be erased during factory reset.
 *
 *         ChipLinuxStorage wraps the storage class ChipLinuxStorageIni with mutex.
 *
 */

#pragma once

#include <platform/Linux/CHIPLinuxStorage.h>
#include <string>

namespace chip {
namespace DeviceLayer {
namespace Internal {

class Storage
{
public:
    static Storage & GetInstance()
    {
        static Storage instance;
        return instance;
    }
    void setDirectory(const char * directory);
    void setFilename(const char * kvs_filename);
    std::string & GetDirectory();
    std::string & GetKVS();

private:
    std::string directory;
    std::string kvs_filename;
};

} // namespace Internal
} // namespace DeviceLayer
} // namespace chip
