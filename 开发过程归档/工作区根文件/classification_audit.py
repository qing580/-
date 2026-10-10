import argparse
import csv
import hashlib
import json
import math
import statistics as st
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path


def number(s):
    try:
        x = float(s)
        return x if math.isfinite(x) else None
    except (ValueError, TypeError):
        return None


def category(t):
    if 70 <= t <= 79: return '货船'
    if 80 <= t <= 89: return '油轮'
    if t == 30: return '渔船'
    if 60 <= t <= 69: return '客船'
    if 40 <= t <= 49: return '高速船'
    if t in (31, 32, 52, 53): return '拖带或港口服务'
    if t in (36, 37): return '帆船或娱乐船'
    return '其他编码'


def distance(a, b):
    p, q = math.radians(a[1]), math.radians(b[1])
    h = math.sin((q-p)/2)**2 + math.cos(p)*math.cos(q)*math.sin(math.radians(b[2]-a[2])/2)**2
    return 6371000 * 2 * math.asin(math.sqrt(min(1, h)))


def write_csv(path, rows):
    if not rows: return
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def run(source, out):
    out.mkdir(parents=True, exist_ok=True)
    with source.open(encoding='utf-8-sig', newline='') as f: rows = list(csv.DictReader(f))
    groups = defaultdict(list)
    for r in rows: groups[r['mmsi']].append(r)
    archive, features, labels = [], [], []
    feature_names = ['speed_mean', 'speed_sd', 'speed_median', 'speed_p90', 'low_speed_fraction', 'speed_change_per_min', 'turn_per_min', 'path_m']
    for mmsi, records in sorted(groups.items()):
        codes = sorted({int(x) for r in records if (x := number(r.get('vessel_type'))) is not None and x == int(x) and 0 < x <= 255})
        cat = category(codes[0]) if len(codes) == 1 else ('编码冲突' if codes else '未知')
        points, invalid = [], 0
        for r in records:
            if r['message_type'] != 'PositionReport': continue
            lat, lon, speed, course = (number(r.get(k)) for k in ('lat','lon','sog','cog'))
            if lat is None or lon is None or speed is None or not (-90 <= lat <= 90 and -180 <= lon <= 180 and 0 <= speed < 102.3):
                invalid += 1
                continue
            points.append((datetime.fromisoformat(r['received_at']), lat, lon, speed, course if course is not None and 0 <= course < 360 else None))
        points = sorted(set(points), key=lambda p: p[0])
        same_time = sum(a[0] == b[0] for a,b in zip(points, points[1:]))
        gaps, acc, turn, path = [], [], [], 0.0
        segments, current = [], []
        for p in points:
            if current and (p[0]-current[-1][0]).total_seconds() > 600:
                segments.append(current)
                current = []
            current.append(p)
        if current: segments.append(current)
        # Extract from the longest gap-bounded segment; no bridging long outages.
        seg = max(segments, key=len, default=[])
        for a,b in zip(points, points[1:]): gaps.append((b[0]-a[0]).total_seconds())
        for a,b in zip(seg, seg[1:]):
            dt = (b[0]-a[0]).total_seconds()
            if dt <= 0: continue
            path += distance(a,b)
            acc.append(abs(b[3]-a[3])*60/dt)
            if a[4] is not None and b[4] is not None and min(a[3],b[3]) >= 1:
                turn.append(abs((b[4]-a[4]+180)%360-180)*60/dt)
        names = '|'.join(sorted({r['vessel_name'].strip() for r in records if r['vessel_name'].strip()}))
        imos = '|'.join(sorted({r['imo'].strip() for r in records if r['imo'].strip() and r['imo'] != '0'}))
        eligible = cat in ('货船','油轮') and len(seg) >= 10 and same_time == 0
        archive.append(dict(MMSI=mmsi,船名=names,IMO=imos,船型码='|'.join(map(str,codes)),报文类别=cat,有效位置点=len(points),无效位置点=invalid,同秒冲突=same_time,观测跨度分钟=round((points[-1][0]-points[0][0]).total_seconds()/60,2) if points else 0,最大间隔秒=max(gaps, default=0),超过十分钟间隔数=sum(g>600 for g in gaps),最长分段点数=len(seg),基线候选=eligible))
        labels.append(dict(MMSI=mmsi,船名=names,IMO=imos,报文类别=cat,标签状态='未外部核验',核验船型='',资料网址='',核验日期='',核验人='',备注=''))
        if eligible:
            v = sorted(p[3] for p in seg)
            features.append(dict(mmsi=mmsi, label=cat, speed_mean=st.mean(v),speed_sd=st.pstdev(v),speed_median=st.median(v),speed_p90=v[int((len(v)-1)*.9)],low_speed_fraction=sum(x<1 for x in v)/len(v),speed_change_per_min=st.mean(acc) if acc else 0,turn_per_min=st.mean(turn) if turn else 0,path_m=path))
    write_csv(out/'船舶档案与轨迹质量.csv', archive)
    write_csv(out/'标签核验表_待人工核验.csv', labels)
    write_csv(out/'货船油轮轨迹特征.csv', features)
    summary = dict(source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),rows=len(rows),ships=len(groups),messages=dict(Counter(r['message_type'] for r in rows)),categories=dict(Counter(r['报文类别'] for r in archive)),eligible=dict(Counter(r['label'] for r in features)))
    from sklearn.dummy import DummyClassifier
    from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import accuracy_score, f1_score, classification_report, confusion_matrix
    import sklearn
    summary['sklearn_version'] = sklearn.__version__
    X = [[r[k] for k in feature_names] for r in features]
    y = [r['label'] for r in features]
    ids = list(range(len(features)))
    trainval, test = train_test_split(ids, test_size=.2, random_state=42, stratify=y)
    train, valid = train_test_split(trainval, test_size=.25, random_state=42, stratify=[y[i] for i in trainval])
    assert not (set(train)&set(test) or set(valid)&set(test) or set(train)&set(valid))
    write_csv(out/'固定船舶划分.csv',[dict(MMSI=features[i]['mmsi'],报文类别=y[i],集合=s) for s,part in [('训练',train),('验证',valid),('测试',test)] for i in part])
    models = {'多数类':DummyClassifier(strategy='most_frequent'), '随机森林':RandomForestClassifier(n_estimators=200,min_samples_leaf=3,class_weight='balanced',random_state=42,n_jobs=2),'梯度提升':GradientBoostingClassifier(n_estimators=100,max_depth=2,random_state=42)}
    metrics, predictions = [], []
    for name, model in models.items():
        model.fit([X[i] for i in train],[y[i] for i in train])
        for split, part in [('验证',valid),('测试',test)]:
            pred = model.predict([X[i] for i in part])
            truth = [y[i] for i in part]
            metrics.append(dict(模型=name,集合=split,船舶数=len(part),准确率=accuracy_score(truth,pred),宏平均F1=f1_score(truth,pred,average='macro')))
            summary[name+split] = dict(report=classification_report(truth,pred,zero_division=0,output_dict=True),class_order=['货船','油轮'],confusion=confusion_matrix(truth,pred,labels=['货船','油轮']).tolist())
            predictions.extend(dict(MMSI=features[i]['mmsi'],集合=split,模型=name,报文标签=y[i],预测=p) for i,p in zip(part,pred))
    write_csv(out/'基线对比_报文标签一致性.csv',metrics)
    write_csv(out/'逐船预测结果.csv',predictions)
    (out/'审计与详细指标.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(summary={k:summary[k] for k in ['rows','ships','categories','eligible']},metrics=metrics),ensure_ascii=False))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--input',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    run(a.input,a.output)
