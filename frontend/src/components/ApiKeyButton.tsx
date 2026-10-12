import { useState } from 'react'
import { Button, Input, Modal, Tag } from 'antd'
import { getApiKey, setApiKey } from '../api/key'

// 密钥入口(Ch12):点开输入平台 API Key,存 localStorage;请求拦截器下次请求自动带上。
// 后端未开启鉴权(app_api_key 为空)时这入口只是摆设,不影响使用。
export default function ApiKeyButton() {
  const [open, setOpen] = useState(false)
  const [val, setVal] = useState('')
  const [saved, setSaved] = useState(!!getApiKey())

  // 打开时回填已存的密钥:否则「明明设过,打开却是空的」很困惑(Ch23)
  const openModal = () => {
    setVal(getApiKey() ?? '')
    setOpen(true)
  }
  const save = () => {
    setApiKey(val.trim())
    setSaved(!!val.trim())
    setOpen(false)
  }
  const clear = () => {
    setApiKey('')
    setSaved(false)
    setVal('')
    setOpen(false)
  }

  return (
    <>
      {/* 不在 Button 里塞 Tag:按钮内嵌标签视觉很脏。改用按钮自身样式表达状态(Ch23) */}
      <Button size="small" type={saved ? 'primary' : 'default'} ghost={saved} onClick={openModal}>
        {saved ? '密钥已设置' : '设置密钥'}
      </Button>
      <Modal
        title="平台 API 密钥"
        open={open}
        onCancel={() => setOpen(false)}
        footer={[
          <Button key="clear" danger onClick={clear} disabled={!saved}>
            清除
          </Button>,
          <Button key="save" type="primary" onClick={save}>
            保存
          </Button>,
        ]}
      >
        {saved && (
          <Tag color="green" style={{ marginBottom: 8 }}>
            当前已设置密钥,可直接修改或清除
          </Tag>
        )}
        <p style={{ color: '#888' }}>
          后端开启鉴权后,所有请求需携带此密钥(仅存本地 localStorage,随请求发给后端)。
        </p>
        <Input.Password
          placeholder="输入平台 API Key"
          value={val}
          onChange={(e) => setVal(e.target.value)}
          onPressEnter={save}
        />
      </Modal>
    </>
  )
}
