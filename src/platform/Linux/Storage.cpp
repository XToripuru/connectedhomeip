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

#include <platform/Linux/Storage.h>
#include <string>

namespace chip {
namespace DeviceLayer {
namespace Internal {

void Storage::setDirectory(const char * new_directory)
{
    directory.assign(new_directory);
}

void Storage::setFilename(const char * new_kvs_filename)
{
    kvs_filename.assign(new_kvs_filename);
}

std::string & Storage::GetDirectory()
{
    return directory;
}

std::string & Storage::GetKVS()
{
    return kvs_filename;
}

} // namespace Internal
} // namespace DeviceLayer
} // namespace chip
