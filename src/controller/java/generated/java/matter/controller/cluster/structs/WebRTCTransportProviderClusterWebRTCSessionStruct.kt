/*
 *
 *    Copyright (c) 2023 Project CHIP Authors
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
package matter.controller.cluster.structs

import java.util.Optional
import matter.controller.cluster.*
import matter.tlv.ContextSpecificTag
import matter.tlv.Tag
import matter.tlv.TlvReader
import matter.tlv.TlvWriter

class WebRTCTransportProviderClusterWebRTCSessionStruct(
  val id: UShort,
  val peerNodeID: ULong,
  val peerEndpointID: UShort,
  val streamUsage: UByte,
  val videoStreamID: UShort?,
  val audioStreamID: UShort?,
  val metadataEnabled: Optional<Boolean>,
  val fabricIndex: UByte,
) {
  override fun toString(): String = buildString {
    append("WebRTCTransportProviderClusterWebRTCSessionStruct {\n")
    append("\tid : $id\n")
    append("\tpeerNodeID : $peerNodeID\n")
    append("\tpeerEndpointID : $peerEndpointID\n")
    append("\tstreamUsage : $streamUsage\n")
    append("\tvideoStreamID : $videoStreamID\n")
    append("\taudioStreamID : $audioStreamID\n")
    append("\tmetadataEnabled : $metadataEnabled\n")
    append("\tfabricIndex : $fabricIndex\n")
    append("}\n")
  }

  fun toTlv(tlvTag: Tag, tlvWriter: TlvWriter) {
    tlvWriter.apply {
      startStructure(tlvTag)
      put(ContextSpecificTag(TAG_ID), id)
      put(ContextSpecificTag(TAG_PEER_NODE_ID), peerNodeID)
      put(ContextSpecificTag(TAG_PEER_ENDPOINT_ID), peerEndpointID)
      put(ContextSpecificTag(TAG_STREAM_USAGE), streamUsage)
      if (videoStreamID != null) {
        put(ContextSpecificTag(TAG_VIDEO_STREAM_ID), videoStreamID)
      } else {
        putNull(ContextSpecificTag(TAG_VIDEO_STREAM_ID))
      }
      if (audioStreamID != null) {
        put(ContextSpecificTag(TAG_AUDIO_STREAM_ID), audioStreamID)
      } else {
        putNull(ContextSpecificTag(TAG_AUDIO_STREAM_ID))
      }
      if (metadataEnabled.isPresent) {
        val optmetadataEnabled = metadataEnabled.get()
        put(ContextSpecificTag(TAG_METADATA_ENABLED), optmetadataEnabled)
      }
      put(ContextSpecificTag(TAG_FABRIC_INDEX), fabricIndex)
      endStructure()
    }
  }

  companion object {
    private const val TAG_ID = 0
    private const val TAG_PEER_NODE_ID = 1
    private const val TAG_PEER_ENDPOINT_ID = 2
    private const val TAG_STREAM_USAGE = 3
    private const val TAG_VIDEO_STREAM_ID = 4
    private const val TAG_AUDIO_STREAM_ID = 5
    private const val TAG_METADATA_ENABLED = 6
    private const val TAG_FABRIC_INDEX = 254

    fun fromTlv(
      tlvTag: Tag,
      tlvReader: TlvReader,
    ): WebRTCTransportProviderClusterWebRTCSessionStruct {
      tlvReader.enterStructure(tlvTag)
      val id = tlvReader.getUShort(ContextSpecificTag(TAG_ID))
      val peerNodeID = tlvReader.getULong(ContextSpecificTag(TAG_PEER_NODE_ID))
      val peerEndpointID = tlvReader.getUShort(ContextSpecificTag(TAG_PEER_ENDPOINT_ID))
      val streamUsage = tlvReader.getUByte(ContextSpecificTag(TAG_STREAM_USAGE))
      val videoStreamID =
        if (!tlvReader.isNull()) {
          tlvReader.getUShort(ContextSpecificTag(TAG_VIDEO_STREAM_ID))
        } else {
          tlvReader.getNull(ContextSpecificTag(TAG_VIDEO_STREAM_ID))
          null
        }
      val audioStreamID =
        if (!tlvReader.isNull()) {
          tlvReader.getUShort(ContextSpecificTag(TAG_AUDIO_STREAM_ID))
        } else {
          tlvReader.getNull(ContextSpecificTag(TAG_AUDIO_STREAM_ID))
          null
        }
      val metadataEnabled =
        if (tlvReader.isNextTag(ContextSpecificTag(TAG_METADATA_ENABLED))) {
          Optional.of(tlvReader.getBoolean(ContextSpecificTag(TAG_METADATA_ENABLED)))
        } else {
          Optional.empty()
        }
      val fabricIndex = tlvReader.getUByte(ContextSpecificTag(TAG_FABRIC_INDEX))

      tlvReader.exitContainer()

      return WebRTCTransportProviderClusterWebRTCSessionStruct(
        id,
        peerNodeID,
        peerEndpointID,
        streamUsage,
        videoStreamID,
        audioStreamID,
        metadataEnabled,
        fabricIndex,
      )
    }
  }
}
