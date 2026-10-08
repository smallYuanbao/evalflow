from backend.db import SessionLocal, init_db
from backend.models import Dataset, DatasetItem


def seed() -> None:
    """造评测集(dataset + items)。run/trace/score 不在这里产生,归 run 生命周期管。"""
    init_db()
    s = SessionLocal()
    ds = Dataset(name="育儿-常见病", description="示例评测集")
    s.add(ds)
    s.flush()

    # expected_output 要点与 knowledge.py 的措辞对齐,recall 是子串匹配
    items = [
        # 易:常规问法(检索能中,recall 应 1.0)
        DatasetItem(dataset_id=ds.id, input="宝宝发烧38度怎么办",
                    expected_output="物理降温/就医/用药", bucket="护理"),
        DatasetItem(dataset_id=ds.id, input="6个月能加辅食吗",
                    expected_output="满6个月/铁米粉", bucket="喂养"),
        DatasetItem(dataset_id=ds.id, input="宝宝晚上总醒怎么回事",
                    expected_output="出牙/睡眠倒退/环境", bucket="睡眠"),
        # 难:KB 缺口(ground truth 多一个库里没有的点,recall 应 0.75)
        DatasetItem(dataset_id=ds.id, input="宝宝发烧38度怎么办需要观察什么",
                    expected_output="物理降温/就医/用药/观察精神状态", bucket="护理"),
        # 难:口语化问法(关键词检索漏,recall 应 0.0)
        DatasetItem(dataset_id=ds.id, input="娃夜里老闹腾不睡觉咋办",
                    expected_output="出牙/睡眠倒退/环境", bucket="睡眠"),
        # 库外:知识库里没有答案,正确行为是拒答(评 rejection,不评 recall)
        DatasetItem(dataset_id=ds.id, input="宝宝拉肚子怎么办",
                    expected_output="", bucket="库外"),
        DatasetItem(dataset_id=ds.id, input="宝宝长湿疹怎么护理",
                    expected_output="", bucket="库外"),
    ]
    s.add_all(items)
    s.commit()
    s.close()


if __name__ == "__main__":
    seed()
