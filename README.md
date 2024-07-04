이온트랩 실험을 위한 파이썬기반 프로그램.
공유 가능한 실험 장비를 여러 실험 셋업에서 활용하기 위해, 공용 장비는 서버 컴퓨터에서 컨트롤하고 클라이언트들이 접근하여 사용하는 방식으로 설계되었음.

실험에 필요한 장비들의 조작 및 실험 진행을 동시다발적으로 진행하기 위하여 대부분의 장비 컨트롤은 multithreading으로 설계되었으나,
CCD 등의 장비는 큰 이미지 데이터의 matrix 연산 등으로 인해 CPU 리소스를 크게 잡아먹는 이유와 DLL을 python에서 proper하게 종료할 수 있는 방법이 없기 때문에 process를 죽이는 방법으로 종료하기 위해 multithreading 대신 multiprocessing으로 대체하였음.

# QtDeviceServer_v2![QtServer_CCD](https://user-images.githubusercontent.com/63301234/201577976-dabd5510-cda7-4268-b748-679d4d4cebab.png)
