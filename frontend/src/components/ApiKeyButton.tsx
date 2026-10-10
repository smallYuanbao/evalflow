import { useState } from 'react'
import { Button, Input, Modal, Tag } from 'antd'
import { getApiKey, setApiKey } from '../api/key'

// 密钥入口(Ch12):点开输入平台 API Key,存 localStorage;请求拦截器下次请求自动带上。
// 后端未开启鉴权(app_api_key 为空)时这入口只是摆设,不影响使用。
export default function ApiKeyButton() {
  const [open, setOpen] = useState(false)
  const [val, setVal] = useState('')
  const [saved, setSaved] = useState(!!getApiKey())

  const save = () => {
    setApiKey(val.trim())
    setSaved(!!val.trim())
    setOpen(false)
    setVal('')
  }
  const clear = () => {
    setApiKey('')
    setSaved(false)
    setOpen(false)
    setVal('')
  }

  return (
    <>
      <Button size="small" onClick={() => setOpen(true)}>
        {saved ? <Tag color="green" style={{ marginInlineEnd: 0 }}>已设密钥</Tag> : '设置密钥'}
      </Button>
      <Modal
        title="平台 API 密钥"
        open={open}
        onOk={save}
        onCancel={() => setOpen(false)}
        okText="保存"
        footer={[
          <Button key="clear" danger onClick={clear}>清除</Button>,
          <Button key="save" type="primary" onClick={save}>保存</Button>,
        ]}
      >
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
